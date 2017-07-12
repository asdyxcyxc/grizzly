import logging
import os
import shutil
import tempfile
import unittest

import corpman


logging.basicConfig(level=logging.DEBUG if bool(os.getenv("DEBUG")) else logging.INFO)
log = logging.getLogger("corpman_test")


class EnvVarCorpman(corpman.CorpusManager):
    key = "envvar"
    def _init_fuzzer(self):
        self.add_required_envvar("RANDOM_ENVAR_TEST")
        self.add_required_envvar("RANDOM_ENVAR_TEST2", "test123")
    def _generate(self, testcase, redirect_page, mime_type=None):
        testcase.add_testfile(corpman.TestFile(testcase.landing_page, redirect_page))
        return testcase

class SimpleCorpman(corpman.CorpusManager):
    key = "simple"
    def _generate(self, testcase, redirect_page, mime_type=None):
        testcase.add_testfile(corpman.TestFile(testcase.landing_page, redirect_page))
        return testcase


class SinglePassCorpman(corpman.CorpusManager):
    key = "single_pass"
    def _init_fuzzer(self):
        self.rotation_period = 1
        self.single_pass = True
    def _generate(self, testcase, redirect_page, mime_type=None):
        testcase.add_testfile(corpman.TestFile(self._active_input.file_name, self._active_input.get_data()))
        testcase.add_testfile(corpman.TestFile(testcase.landing_page, redirect_page))
        return testcase


class CorpusManagerTests(unittest.TestCase):

    def test_0(self):
        "test a basic corpus manager"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            # create template
            template_file = os.path.join(corp_dir, "test_template.bin")
            with open(template_file, "wb") as fp:
                fp.write("template_data")
            # create corpman
            cm = SimpleCorpman(corp_dir)
            self.assertEqual(cm.key, "simple")
            self.assertEqual(cm.size(), 1) # we only added one template
            self.assertEqual(cm.get_active_file_name(), None) # None since generate() has not been called
            self.assertEqual(cm.landing_page(), "test_page_0000.html")
            self.assertEqual(cm.landing_page(transition=True), "next_test")
            self.assertEqual(cm.launch_count, 0) # should default to 0 and be incremented by grizzly.py
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_1(self):
        "test CorpusManager generate() creates TestCases and TestFiles using SimpleCorpman"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        tc_dir = tempfile.mkdtemp(prefix="tc_")
        try:
            template_file = os.path.join(corp_dir, "test_template.bin")
            with open(template_file, "wb") as fp:
                fp.write("template_data")
            cm = SimpleCorpman(corp_dir)
            self.assertEqual(cm.landing_page(), "test_page_0000.html")
            tc = cm.generate()
            # check for transition redirect
            self.assertEqual("next_test", cm.get_redirects()[0]["url"])
            # make sure we move forwarded when generate() is called
            self.assertEqual(cm.landing_page(), "test_page_0001.html")
            self.assertEqual(cm.get_active_file_name(), template_file)
            self.assertIsInstance(tc, corpman.TestCase)
            self.assertEqual(tc.landing_page, "test_page_0000.html")
            tc.dump(tc_dir, include_details=True)
            dumped_tf = os.listdir(tc_dir) # dumped test files
            self.assertIn("test_page_0000.html", dumped_tf)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)
            if os.path.isdir(tc_dir):
                shutil.rmtree(tc_dir)

    def test_2(self):
        "test CorpusManager multiple calls to generate() and template rotation"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            selected_templates = set()
            # create templates
            for i in range(10):
                with open(os.path.join(corp_dir, "test_template_%d.bin" % i), "wb") as fp:
                    fp.write("template_data_%d" % i)
            cm = SimpleCorpman(corp_dir)
            cm.rotation_period = 1
            for i in range(50):
                self.assertEqual(cm.landing_page(), "test_page_%04d.html" % i)
                tc = cm.generate()
                self.assertEqual(cm.landing_page(), "test_page_%04d.html" % (i+1))
                selected_templates.add(cm.get_active_file_name())
            # make sure we rotate templates
            self.assertGreater(len(selected_templates), 1)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_3(self):
        "test CorpusManager single pass mode"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            selected_templates = set()
            # create templates
            template_count = 10
            for i in range(template_count):
                with open(os.path.join(corp_dir, "test_template_%d.bin" % i), "wb") as fp:
                    fp.write("template_data_%d" % i)
            cm = SinglePassCorpman(corp_dir)
            self.assertEqual(cm.size(), template_count)
            for _ in range(template_count):
                tc = cm.generate()
                self.assertEqual(len(tc._test_files), 2)
                selected_templates.add(cm.get_active_file_name())
            # make sure we cover all the input files
            self.assertEqual(len(selected_templates), template_count)
            self.assertEqual(cm.size(), 0)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_4(self):
        "test single template file"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            selected_templates = set()
            # create templates
            for i in range(10):
                with open(os.path.join(corp_dir, "test_template_%d.bin" % i), "wb") as fp:
                    fp.write("template_data_%d" % i)
            cm = SimpleCorpman(os.path.join(corp_dir, "test_template_0.bin"))
            self.assertEqual(cm.size(), 1)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_5(self):
        "test multiple template files in nested directories"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        nd_1 = tempfile.mkdtemp(prefix="test1_", dir=corp_dir)
        nd_2 = tempfile.mkdtemp(prefix="test2_", dir=corp_dir)
        try:
            # create templates
            template_count = 10
            for i in range(template_count):
                with open(os.path.join(nd_1, "test_template_%d.bin" % i), "wb") as fp:
                    fp.write("template_data_%d" % i)
            for i in range(template_count):
                with open(os.path.join(nd_2, "test_template_%d.bin" % i), "wb") as fp:
                    fp.write("template_data_%d" % i)
            cm = SimpleCorpman(corp_dir)
            self.assertEqual(cm.size(), template_count*2)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_6(self):
        "test multiple template files with extension filter"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            # create templates
            for i in range(10):
                with open(os.path.join(corp_dir, "test_template_%d.bad" % i), "wb") as fp:
                    fp.write("template_data_%d" % i)
            with open(os.path.join(corp_dir, "test_template.good"), "wb") as fp:
                fp.write("template_data")
            cm = SimpleCorpman(corp_dir, accepted_extensions=["good"])
            self.assertEqual(cm.size(), 1)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_7(self):
        "test ignore empty template files and blacklisted files"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            # create templates
            with open(os.path.join(corp_dir, "test_template.good"), "wb") as fp:
                fp.write("template_data")
            with open(os.path.join(corp_dir, "test_template.empty"), "wb") as fp:
                fp.write("")
            with open(os.path.join(corp_dir, ".somefile"), "wb") as fp:
                fp.write("template_data")
            # /me crosses fingers and hopes this test doesn't break something on Windows...
            with open(os.path.join(corp_dir, "thumbs.db"), "wb") as fp:
                fp.write("template_data")
            cm = SimpleCorpman(corp_dir)
            self.assertEqual(cm.size(), 1)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_8(self):
        "test extension filter normalization"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            # create templates
            with open(os.path.join(corp_dir, "test_template.bad"), "wb") as fp:
                fp.write("template_data")

            with open(os.path.join(corp_dir, "test_template1.good"), "wb") as fp:
                fp.write("template_data")

            with open(os.path.join(corp_dir, "test_template2.GOOD"), "wb") as fp:
                fp.write("template_data")

            with open(os.path.join(corp_dir, "test_template2.GReat"), "wb") as fp:
                fp.write("template_data")

            cm = SimpleCorpman(corp_dir, accepted_extensions=["good", ".greaT"])
            self.assertEqual(cm.size(), 3)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_9(self):
        "test corpus manager with default harness"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        tc_dir = tempfile.mkdtemp(prefix="tc_")
        try:
            # create templates
            with open(os.path.join(corp_dir, "test_template.bin"), "wb") as fp:
                fp.write("template_data")

            cm = SimpleCorpman(corp_dir)
            cm.enable_harness()
            self.assertEqual(cm.landing_page(harness=True), "grizzly_fuzz_harness.html")
            self.assertEqual(cm.size(), 1)

            expected_test = cm.landing_page()
            tc = cm.generate()
            tc.dump(tc_dir)

            # verify test files
            dumped_tf = os.listdir(tc_dir) # dumped test files
            self.assertEqual(len(dumped_tf), 2) # expect test and harness
            self.assertIn(expected_test, dumped_tf)
            self.assertIn(cm.landing_page(harness=True), dumped_tf)

            # verify redirects
            redirs = cm.get_redirects()
            self.assertEqual(len(redirs), 2)
            r_count = 0
            for redir in redirs:
                self.assertIn(redir["url"], ["next_test", "first_test"])
                if redir["url"] == "first_test":
                    self.assertEqual(redir["file_name"], expected_test)
                elif redir["url"] == "next_test":
                    self.assertEqual(redir["file_name"], cm.landing_page())
                if redir["required"]:
                    r_count += 1
            self.assertEqual(r_count, 1)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)
            if os.path.isdir(tc_dir):
                shutil.rmtree(tc_dir)

    def test_10(self):
        "test corpus manager landing_page() without a harness"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            # create templates
            with open(os.path.join(corp_dir, "test_template.bin"), "wb") as fp:
                fp.write("template_data")

            cm = SimpleCorpman(corp_dir)
            self.assertIn(cm.landing_page(harness=True), "test_page_0000.html")

        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_11(self):
        "test get/set and reset redirects"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            # create templates
            with open(os.path.join(corp_dir, "test_template.bin"), "wb") as fp:
                fp.write("template_data")
            cm = SimpleCorpman(corp_dir)
            test_redirs = (
                ("url1", "file1", True),
                ("url2", "file2", False),
                ("url3", "file3", True),
                ("url3", "file4", False))
            for url, name, reqd in test_redirs:
                cm._set_redirect(url, name, reqd)
            results = cm.get_redirects()
            self.assertEqual(len(results), 3)
            f_count = 0
            t_count = 0
            for redir in results:
                if redir["required"]:
                    t_count += 1
                else:
                    f_count += 1
            self.assertEqual(t_count, 1)
            cm.generate()
            self.assertEqual(f_count, 2)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_12(self):
        "test get/set includes"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        inc_dir = tempfile.mkdtemp(prefix="inc_")
        try:
            # create templates
            with open(os.path.join(corp_dir, "dummy_template.bin"), "wb") as fp:
                fp.write("template_data")

            cm = SimpleCorpman(corp_dir)
            cm._add_include("/", inc_dir)
            with self.assertRaises(IOError):
                cm._add_include("bad_path", "/does_not_exist/asdf")

            results = cm.get_includes()
            self.assertEqual(len(results), 1)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)
            if os.path.isdir(inc_dir):
                shutil.rmtree(inc_dir)

    def test_13(self):
        "test get/set and reset dynamic responses (callbacks)"
        def test_callback():
            return "PASS"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            # create templates
            with open(os.path.join(corp_dir, "test_template.bin"), "wb") as fp:
                fp.write("template_data")
            cm = SimpleCorpman(corp_dir)
            cm._add_dynamic_response("test_url", test_callback, mime_type="text/plain")
            results = cm.get_dynamic_responses()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["callback"](), "PASS")
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_14(self):
        "test adding test files in nested directories"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        tc_dir = tempfile.mkdtemp(prefix="tc_")
        try:
            template_file = os.path.join(corp_dir, "test_template.bin")
            with open(template_file, "wb") as fp:
                fp.write("template_data")
            cm = SimpleCorpman(corp_dir)
            tc = cm.generate()
            test_file_path = "test/dir/path/file.txt"
            tc.add_testfile(corpman.TestFile(test_file_path, "somedata"))
            tc.dump(tc_dir)
            self.assertTrue(os.path.isfile(os.path.join(tc_dir, test_file_path)))
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)
            if os.path.isdir(tc_dir):
                shutil.rmtree(tc_dir)

    def test_15(self):
        "test InputFile object"
        tc_dir = tempfile.mkdtemp(prefix="tc_")
        t_file = os.path.join(tc_dir, "testfile.bin")
        with open(t_file, "w") as tf:
            tf.write("test")
        in_file = corpman.InputFile(t_file)
        try:
            self.assertEqual(in_file.extension, "bin")
            self.assertEqual(in_file.file_name, t_file)
            self.assertEqual(in_file.get_data(), "test")
        finally:
            if os.path.isdir(tc_dir):
                shutil.rmtree(tc_dir)

    def test_16(self):
        "test empty InputFile object"
        with self.assertRaises(IOError):
            corpman.InputFile("foo/bar/none")

    def test_17(self):
        "test TestCase object"
        tf1 = corpman.TestFile("testfile1.bin", "test_req")
        tf2 = corpman.TestFile("test_dir/testfile2.bin", "test_nreq", required=False)
        tc = corpman.TestCase("land_page", "corp_name", input_fname="testfile1.bin")
        tc.add_testfile(tf1)
        tc.add_testfile(tf2)
        opt_files = tc.get_optional()
        self.assertEqual(len(opt_files), 1)
        self.assertTrue("test_dir/testfile2.bin" in opt_files)
        tc_dir = tempfile.mkdtemp(prefix="tc_")
        try:
            tc.dump(tc_dir, include_details=True)
            self.assertTrue(os.path.isfile(os.path.join(tc_dir, "test_info.txt")))
            self.assertTrue(os.path.isdir(os.path.join(tc_dir, "test_dir")))
            self.assertTrue(os.path.isfile(os.path.join(tc_dir, "test_dir/testfile2.bin")))
            with open(os.path.join(tc_dir, "testfile1.bin"), "r") as test_fp:
                self.assertEqual(test_fp.read(), "test_req")
        finally:
            shutil.rmtree(tc_dir)

    def test_18(self):
        "test a rotation period of 0 with single_pass true"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            selected_templates = set()
            with open(os.path.join(corp_dir, "test_template.bin"), "wb") as fp:
                fp.write("a")
            cm = SinglePassCorpman(corp_dir)
            cm.rotation_period = 0
            with self.assertRaises(AssertionError):
                cm.generate()
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_19(self):
        "test a negative rotation period"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            selected_templates = set()
            with open(os.path.join(corp_dir, "test_template.bin"), "wb") as fp:
                fp.write("a")
            cm = SimpleCorpman(corp_dir)
            cm.rotation_period = -1
            with self.assertRaises(AssertionError):
                cm.generate()
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_20(self):
        "test missing an environment variable check"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        try:
            # create template
            template_file = os.path.join(corp_dir, "test_template.bin")
            with open(template_file, "wb") as fp:
                fp.write("template_data")
            with self.assertRaisesRegexp(RuntimeError, "Missing environment variable!.+"):
                cm = EnvVarCorpman(corp_dir)
        finally:
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)

    def test_21(self):
        "test environment variable & files are dumped"
        corp_dir = tempfile.mkdtemp(prefix="crp_")
        tc_dir = tempfile.mkdtemp(prefix="tc_")
        prf_dir = tempfile.mkdtemp(prefix="prf_")
        try:
            # create template
            template_file = os.path.join(corp_dir, "test_template.bin")
            with open(template_file, "wb") as fp:
                fp.write("template_data")
            os.environ["RANDOM_ENVAR_TEST"] = "anything!"
            os.environ["RANDOM_ENVAR_TEST2"] = "test123"
            cm = EnvVarCorpman(corp_dir)
            tc = cm.generate()
            env_file = os.path.join(prf_dir, "simple_prefs.js")
            with open(env_file, "wb") as fp:
                fp.write("stuff.blah=1;")
            tc.add_environ_file("prefs.js", env_file)
            tc.dump(tc_dir, include_details=True)
            dumped_tf = os.listdir(tc_dir)
            self.assertIn("prefs.js", dumped_tf)
            self.assertIn("env_vars.txt", dumped_tf)
            with open(os.path.join(tc_dir, "env_vars.txt"), "r") as fp:
                vars = fp.read()
            self.assertRegexpMatches(vars, "RANDOM_ENVAR_TEST=")
            self.assertRegexpMatches(vars, "RANDOM_ENVAR_TEST2=test123")
        finally:
            os.environ.pop("RANDOM_ENVAR_TEST", None)
            os.environ.pop("RANDOM_ENVAR_TEST2", None)
            if os.path.isdir(corp_dir):
                shutil.rmtree(corp_dir)
            if os.path.isdir(tc_dir):
                shutil.rmtree(tc_dir)
            if os.path.isdir(prf_dir):
                shutil.rmtree(prf_dir)


class LoaderTests(unittest.TestCase):
    def test_0(self):
        "test loader"
        pass # TODO

