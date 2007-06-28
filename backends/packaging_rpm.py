'''A partial apport.PackageInfo class implementation for RPM, as found in 
Fedora, RHEL, SuSE, and many other distributions.

Copyright (C) 2007 Red Hat Inc.
Author: Will Woods <wwoods@redhat.com>

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
the full text of the license.
'''

# N.B. There's some distro-specific bits in here (e.g. is_distro_package()).
# So this is actually an abstract base class (or a template, if you like) for
# RPM-based distributions.
# A proper implementation needs to (at least) set official_keylist to a list 
# of GPG keyids used by official packages. You might have to extend
# is_distro_package() as well, if you don't sign all your official packages 
# (cough cough Fedora rawhide cough)

# It'd be convenient to use rpmUtils from yum, but I'm trying to keep this
# class distro-agnostic.
import rpm, md5, os, stat

class RPMPackageInfo:
    '''Partial apport.PackageInfo class implementation for RPM, as
    found in Fedora, RHEL, CentOS, etc.'''

    # Empty keylist. Should contain a list of key ids (8 lowercase hex digits).
    # e.g. official_keylist = ('30c9ecf8','4f2a6fd2','897da07a','1ac70ce6')
    official_keylist = () 

    def __init__(self):
        self.ts = rpm.TransactionSet() # connect to the rpmdb

    def get_version(self, package):
        '''Return the installed version of a package.'''
        hdr = self._get_header(package)
        # Note - "version" here seems to refer to the full EVR, so..
        return hdr.dsOfHeader().EVR()

    def get_dependencies(self, package):
        '''Return a list of packages a package depends on.'''
        hdr = self._get_header(package)
        # parse this package's Requires
        reqs=[]
        for r in hdr['requires']:
            if r.startswith('rpmlib'):
                continue # we've got rpmlib, thanks
            if r[0] == '/': # file requires
                req_heads = self._get_headers_by_tag('basenames',r)
            else:           # other requires
                req_heads = self._get_headers_by_tag('provides',r)
            for rh in req_heads:
                rh_envra = self._make_envra_from_header(rh)
                if rh_envra not in reqs:
                    reqs.append(rh_envra)
        return reqs

    def get_source(self, package):
        '''Return the source package name for a package.'''
        hdr = self._get_header(package)
        return hdr['sourcerpm']
        
    def get_architecture(self, package):
        '''Return the architecture of a package.

        This might differ on multiarch architectures (e. g.  an i386 Firefox
        package on a x86_64 system)'''
        # Yeah, this is kind of redundant, as package is ENVRA, but I want
        # to do this the right way (in case we change what 'package' is)
        hdr = self._get_header(package)
        return hdr['arch']

    def get_files(self, package):
        '''Return list of files shipped by a package.'''
        hdr = self._get_header(package)
        files = []
        for (f, mode) in zip(hdr['filenames'],hdr['filemodes']):
            if not stat.S_ISDIR(mode):
                files.append(f)
        return files

    def get_modified_files(self, package):
        '''Return list of all modified files of a package.'''
        hdr = self._get_header(package)

        files  = hdr['filenames']
        mtimes = hdr['filemtimes']
        md5s   = hdr['filemd5s']

        modified = []
        for i in xrange(len(files)):
            # Skip files we're not tracking md5s for
            if not md5s[i]: continue
            # Skip files we can't read
            if not os.access(files[i],os.R_OK): continue
            # Skip things that aren't real files
            s = os.stat(files[i])
            if not stat.S_ISREG(s.st_mode): continue
            # Skip things that haven't been modified
            if mtimes[i] == s.st_mtime: continue
            # Oh boy, an actual possibly-modified file. Check the md5sum!
            if not self._checkmd5(files[i],md5s[i]):
                modified.append(files[i])

        return modified

    def get_file_package(self, file):
        '''Return the package a file belongs to, or None if the file is not
        shipped by any package.
        
        Under normal use, the 'file' argument will always be the executable
        that crashed.
        '''
        # In debian-land, the name of the package is unique enough to identify
        # it, but here in RPMville we have multilib. So we need to identify
        # packages by ENVRA to guarantee uniqueness.
        # Here's the sad part - one quirk of our multilib implementation is
        # that a file can belong to multiple packages. So which one do we
        # choose? If we had context from the crash dump we might know which
        # arch was the important one, but for now.. let's just use the system
        # arch.
        # TODO: provide extra context info (arch?) from the crash dump
        hdrs = self._get_headers_by_tag('basenames',file)
        h = None
        if len(hdrs) > 1: # Multiple files own this package - multiarch!
            for h in hdrs:
                if h['arch'] == self.get_system_architecture():
                    break
        else:
            h = hdrs[0]
        return self._make_envra_from_header(h) 

    def get_system_architecture(self):
        '''Return the architecture of the system, in the notation used by the
        particular distribution.'''
        # FIXME is there an rpmlib method for this?
        f = open('/etc/rpm/platform')
        line = f.readline()
        f.close()
        (arch,vendor,os) = line.split('-')
        return arch 

    def is_distro_package(self, package):
        '''Check if a package is a genuine distro package (True) or comes from
        a third-party source.'''
        # This is a list of official keys, set by the concrete subclass
        if not self.official_keylist:
            raise Exception, 'Subclass the RPM implementation for your distro!'
        hdr = self._get_header(package)
        # Check the GPG sig and key ID to see if this package was signed 
        # with an official key.
        if hdr['siggpg']:
            # Package is signed
            keyid = hdr['siggpg'][13:17].encode('hex')
            if keyid in self.official_keylist:
                return True
        return False

    #
    # Internal helper methods. These are only single-underscore, so you can use
    # use them in extending/overriding the methods above in your subclasses
    #

    def _get_headers_by_tag(self,tag,arg):
        '''Get a list of RPM headers by doing dbMatch on the given tag and
        argument.'''
        matches = self.ts.dbMatch(tag,arg)
        if matches.count() == 0:
            raise ValueError, 'Could not find package with %s: %s' % (tag,arg)
        return [m for m in matches]

    def _get_header(self,envra):
        '''Get the RPM header that matches the given ENVRA.'''
        (e,n,v,r,a) = self._split_envra(envra)
        mi = self.ts.dbMatch('name',n) # First, find stuff with the right name
        # Now we narrow using the EVRA
        args = {'epoch':e,'version':v,'release':r,'arch':a}
        for name,val in args.items():
            if val:
                mi.pattern(name,rpm.RPMMIRE_STRCMP,val)
        hdrs = [m for m in mi]
        # Unless there's some rpmdb breakage, you should have one header
        # here. If you do manage to have two rpms with the same ENVRA,
        # who cares which one you get?
        return hdrs[0]

    def _make_envra_from_header(self,h):
        '''Generate an ENVRA string from an rpm header'''
        nvra="%s-%s-%s.%s" % (h['n'],h['v'],h['r'],h['arch'])
        if h['e']:
            envra = "%s:%s" % (h['e'],nvra)
        else:
            envra = nvra
        return envra

    def _split_envra(self,envra):
        '''Split an ENVRA string into its component parts. e.g.:
        evolution-2.8.3-2.fc6.i386 -> 0, evolution, 2.8.3, 2.fc6, i386
        2:gaim-2.0.0-0.31.beta6.fc6.i386 -> 2, gaim, 2.0.0, 0.31.beta6.fc6, i386
        This code comes from yum's rpmUtils/miscutils.py. Thanks, Seth!'''
        archIndex = envra.rfind('.')
        arch = envra[archIndex+1:]
    
        relIndex = envra[:archIndex].rfind('-')
        rel = envra[relIndex+1:archIndex]
    
        verIndex = envra[:relIndex].rfind('-')
        ver = envra[verIndex+1:relIndex]
    
        epochIndex = envra.find(':')
        if epochIndex == -1:
            epoch = None
        else:
            epoch = envra[:epochIndex]
    
        name = envra[epochIndex + 1:verIndex]
        return epoch, name, ver, rel, arch
    
    def _checkmd5(self,filename,filemd5):
        '''Internal function to check a file's md5sum'''
        m = md5.new()
        f = open(filename)
        data = f.read() 
        f.close()
        m.update(data)
        return (filemd5 == m.hexdigest())

#
# Unit test
#

# FIXME these are way broken right now

if __name__ == '__main__':
    import unittest, tempfile, shutil

    class _DpkgPackageInfoTest(unittest.TestCase):

        def test_get_field(self):
            '''Test _get_field().'''

            data = '''Package: foo
Version: 1.2-3
Depends: libc6 (>= 2.4), libfoo,
 libbar (<< 3),
 libbaz
Conflicts: fu
Description: Test
 more
'''
            self.assertEqual(impl._get_field(data, 'Nonexisting'), None)
            self.assertEqual(impl._get_field(data, 'Version'), '1.2-3')
            self.assertEqual(impl._get_field(data, 'Conflicts'), 'fu')
            self.assertEqual(impl._get_field(data, 'Description'),
                'Test more')
            self.assertEqual(impl._get_field(data, 'Depends'),
                'libc6 (>= 2.4), libfoo, libbar (<< 3), libbaz')

        def test_check_files_md5(self):
            '''Test _check_files_md5().'''

            td = tempfile.mkdtemp()
            try:
                f1 = os.path.join(td, 'test 1.txt')
                f2 = os.path.join(td, 'test:2.txt')
                sumfile = os.path.join(td, 'sums.txt')
                open(f1, 'w').write('Some stuff')
                open(f2, 'w').write('More stuff')
                # use one relative and one absolute path in checksums file
                open(sumfile, 'w').write('''2e41290da2fa3f68bd3313174467e3b5  %s
        f6423dfbc4faf022e58b4d3f5ff71a70  %s
        ''' % (f1[1:], f2))
                self.assertEqual(impl._check_files_md5(sumfile), [], 'correct md5sums')

                open(f1, 'w').write('Some stuff!')
                self.assertEqual(impl._check_files_md5(sumfile), [f1[1:]], 'file 1 wrong')
                open(f2, 'w').write('More stuff!')
                self.assertEqual(impl._check_files_md5(sumfile), [f1[1:], f2], 'files 1 and 2 wrong')
                open(f1, 'w').write('Some stuff')
                self.assertEqual(impl._check_files_md5(sumfile), [f2], 'file 2 wrong')

                # check using a direct md5 list as argument
                self.assertEqual(impl._check_files_md5(open(sumfile).read()),
                    [f2], 'file 2 wrong')

            finally:
                shutil.rmtree(td)

        def test_get_version(self):
            '''Test get_version().'''

            self.assert_(impl.get_version('libc6').startswith('2'))
            self.assertRaises(ValueError, impl.get_version, 'nonexisting')

        def test_get_dependencies(self):
            '''Test get_dependencies().'''

            # package with both Depends: and Pre-Depends:
            d  = impl.get_dependencies('bash')
            self.assert_(len(d) > 2)
            self.assert_('libc6' in d)
            for dep in d:
                self.assert_(impl.get_version(dep))

            # Pre-Depends: only
            d  = impl.get_dependencies('coreutils')
            self.assert_(len(d) >= 1)
            self.assert_('libc6' in d)
            for dep in d:
                self.assert_(impl.get_version(dep))

            # Depends: only
            d  = impl.get_dependencies('libc6')
            self.assert_(len(d) >= 1)
            for dep in d:
                self.assert_(impl.get_version(dep))

        def test_get_source(self):
            '''Test get_source().'''

            self.assertRaises(ValueError, impl.get_source, 'nonexisting')
            self.assertEqual(impl.get_source('bash'), 'bash')
            self.assertEqual(impl.get_source('libc6'), 'glibc')

        def test_get_architecture(self):
            '''Test get_architecture().'''

            self.assertRaises(ValueError, impl.get_architecture, 'nonexisting')
            # just assume that bash uses the native architecture
            d = subprocess.Popen(['dpkg', '--print-architecture'],
                stdout=subprocess.PIPE)
            system_arch = d.communicate()[0].strip()
            assert d.returncode == 0
            self.assertEqual(impl.get_architecture('bash'), system_arch)

        def test_get_files(self):
            '''Test get_files().'''

            self.assertRaises(ValueError, impl.get_files, 'nonexisting')
            self.assert_('/bin/bash' in impl.get_files('bash'))

        def test_get_file_package(self):
            '''Test get_file_package() on normal files.'''

            self.assertEqual(impl.get_file_package('/bin/bash'), 'bash')
            self.assertEqual(impl.get_file_package('/bin/cat'), 'coreutils')
            self.assertEqual(impl.get_file_package('/nonexisting'), None)

        def test_get_file_package_diversion(self):
            '''Test get_file_package() for a diverted file.'''

            # pick first diversion we have
            p = subprocess.Popen('LC_ALL=C dpkg-divert --list | head -n 1',
                shell=True, stdout=subprocess.PIPE)
            out = p.communicate()[0]
            assert p.returncode == 0
            assert out
            fields = out.split()
            file = fields[2]
            pkg = fields[-1]

            self.assertEqual(impl.get_file_package(file), pkg)

        def test_get_system_architecture(self):
            '''Test get_system_architecture().'''

            arch = impl.get_system_architecture()
            # must be nonempty without line breaks
            self.assertNotEqual(arch, '')
            self.assert_('\n' not in arch)

    # only execute if dpkg is available
    try:
        if subprocess.call(['dpkg', '--help'], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE) == 0:
            unittest.main()
    except OSError:
        pass

