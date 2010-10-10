import py, sys
from pytest.plugin import pytest_python as funcargs

class TestModule:
    def test_module_file_not_found(self, testdir):
        tmpdir = testdir.tmpdir
        fn = tmpdir.join('nada','no')
        col = py.test.collect.Module(fn, config=testdir.Config())
        col.config = testdir.parseconfig(tmpdir)
        py.test.raises(py.error.ENOENT, col.collect)

    def test_failing_import(self, testdir):
        modcol = testdir.getmodulecol("import alksdjalskdjalkjals")
        py.test.raises(ImportError, modcol.collect)
        py.test.raises(ImportError, modcol.collect)
        py.test.raises(ImportError, modcol.run)

    def test_import_duplicate(self, testdir):
        a = testdir.mkdir("a")
        b = testdir.mkdir("b")
        p = a.ensure("test_whatever.py")
        p.pyimport()
        del py.std.sys.modules['test_whatever']
        b.ensure("test_whatever.py")
        result = testdir.runpytest()
        result.stdout.fnmatch_lines([
            "*import*mismatch*",
            "*imported*test_whatever*",
            "*%s*" % a.join("test_whatever.py"),
            "*not the same*",
            "*%s*" % b.join("test_whatever.py"),
            "*HINT*",
        ])

    def test_syntax_error_in_module(self, testdir):
        modcol = testdir.getmodulecol("this is a syntax error")
        py.test.raises(modcol.CollectError, modcol.collect)
        py.test.raises(modcol.CollectError, modcol.collect)
        py.test.raises(modcol.CollectError, modcol.run)

    def test_module_considers_pluginmanager_at_import(self, testdir):
        modcol = testdir.getmodulecol("pytest_plugins='xasdlkj',")
        py.test.raises(ImportError, "modcol.obj")

class TestClass:
    def test_class_with_init_not_collected(self, testdir):
        modcol = testdir.getmodulecol("""
            class TestClass1:
                def __init__(self):
                    pass
            class TestClass2(object):
                def __init__(self):
                    pass
        """)
        l = modcol.collect()
        assert len(l) == 0

class TestGenerator:
    def test_generative_functions(self, testdir):
        modcol = testdir.getmodulecol("""
            def func1(arg, arg2):
                assert arg == arg2

            def test_gen():
                yield func1, 17, 3*5
                yield func1, 42, 6*7
        """)
        colitems = modcol.collect()
        assert len(colitems) == 1
        gencol = colitems[0]
        assert isinstance(gencol, py.test.collect.Generator)
        gencolitems = gencol.collect()
        assert len(gencolitems) == 2
        assert isinstance(gencolitems[0], py.test.collect.Function)
        assert isinstance(gencolitems[1], py.test.collect.Function)
        assert gencolitems[0].name == '[0]'
        assert gencolitems[0].obj.__name__ == 'func1'

    def test_generative_methods(self, testdir):
        modcol = testdir.getmodulecol("""
            def func1(arg, arg2):
                assert arg == arg2
            class TestGenMethods:
                def test_gen(self):
                    yield func1, 17, 3*5
                    yield func1, 42, 6*7
        """)
        gencol = modcol.collect()[0].collect()[0].collect()[0]
        assert isinstance(gencol, py.test.collect.Generator)
        gencolitems = gencol.collect()
        assert len(gencolitems) == 2
        assert isinstance(gencolitems[0], py.test.collect.Function)
        assert isinstance(gencolitems[1], py.test.collect.Function)
        assert gencolitems[0].name == '[0]'
        assert gencolitems[0].obj.__name__ == 'func1'

    def test_generative_functions_with_explicit_names(self, testdir):
        modcol = testdir.getmodulecol("""
            def func1(arg, arg2):
                assert arg == arg2

            def test_gen():
                yield "seventeen", func1, 17, 3*5
                yield "fortytwo", func1, 42, 6*7
        """)
        colitems = modcol.collect()
        assert len(colitems) == 1
        gencol = colitems[0]
        assert isinstance(gencol, py.test.collect.Generator)
        gencolitems = gencol.collect()
        assert len(gencolitems) == 2
        assert isinstance(gencolitems[0], py.test.collect.Function)
        assert isinstance(gencolitems[1], py.test.collect.Function)
        assert gencolitems[0].name == "['seventeen']"
        assert gencolitems[0].obj.__name__ == 'func1'
        assert gencolitems[1].name == "['fortytwo']"
        assert gencolitems[1].obj.__name__ == 'func1'

    def test_generative_functions_unique_explicit_names(self, testdir):
        # generative
        modcol = testdir.getmodulecol("""
            def func(): pass
            def test_gen():
                yield "name", func
                yield "name", func
        """)
        colitems = modcol.collect()
        assert len(colitems) == 1
        gencol = colitems[0]
        assert isinstance(gencol, py.test.collect.Generator)
        py.test.raises(ValueError, "gencol.collect()")

    def test_generative_methods_with_explicit_names(self, testdir):
        modcol = testdir.getmodulecol("""
            def func1(arg, arg2):
                assert arg == arg2
            class TestGenMethods:
                def test_gen(self):
                    yield "m1", func1, 17, 3*5
                    yield "m2", func1, 42, 6*7
        """)
        gencol = modcol.collect()[0].collect()[0].collect()[0]
        assert isinstance(gencol, py.test.collect.Generator)
        gencolitems = gencol.collect()
        assert len(gencolitems) == 2
        assert isinstance(gencolitems[0], py.test.collect.Function)
        assert isinstance(gencolitems[1], py.test.collect.Function)
        assert gencolitems[0].name == "['m1']"
        assert gencolitems[0].obj.__name__ == 'func1'
        assert gencolitems[1].name == "['m2']"
        assert gencolitems[1].obj.__name__ == 'func1'

    def test_order_of_execution_generator_same_codeline(self, testdir, tmpdir):
        o = testdir.makepyfile("""
            def test_generative_order_of_execution():
                import py
                test_list = []
                expected_list = list(range(6))

                def list_append(item):
                    test_list.append(item)

                def assert_order_of_execution():
                    py.builtin.print_('expected order', expected_list)
                    py.builtin.print_('but got       ', test_list)
                    assert test_list == expected_list

                for i in expected_list:
                    yield list_append, i
                yield assert_order_of_execution
        """)
        reprec = testdir.inline_run(o)
        passed, skipped, failed = reprec.countoutcomes()
        assert passed == 7
        assert not skipped and not failed

    def test_order_of_execution_generator_different_codeline(self, testdir):
        o = testdir.makepyfile("""
            def test_generative_tests_different_codeline():
                import py
                test_list = []
                expected_list = list(range(3))

                def list_append_2():
                    test_list.append(2)

                def list_append_1():
                    test_list.append(1)

                def list_append_0():
                    test_list.append(0)

                def assert_order_of_execution():
                    py.builtin.print_('expected order', expected_list)
                    py.builtin.print_('but got       ', test_list)
                    assert test_list == expected_list

                yield list_append_0
                yield list_append_1
                yield list_append_2
                yield assert_order_of_execution
        """)
        reprec = testdir.inline_run(o)
        passed, skipped, failed = reprec.countoutcomes()
        assert passed == 4
        assert not skipped and not failed

class TestFunction:
    def test_getmodulecollector(self, testdir):
        item = testdir.getitem("def test_func(): pass")
        modcol = item.getparent(py.test.collect.Module)
        assert isinstance(modcol, py.test.collect.Module)
        assert hasattr(modcol.obj, 'test_func')

    def test_function_equality(self, testdir, tmpdir):
        config = testdir.reparseconfig()
        f1 = py.test.collect.Function(name="name", config=config,
                                      args=(1,), callobj=isinstance)
        f2 = py.test.collect.Function(name="name",config=config,
                                      args=(1,), callobj=py.builtin.callable)
        assert not f1 == f2
        assert f1 != f2
        f3 = py.test.collect.Function(name="name", config=config,
                                      args=(1,2), callobj=py.builtin.callable)
        assert not f3 == f2
        assert f3 != f2

        assert not f3 == f1
        assert f3 != f1

        f1_b = py.test.collect.Function(name="name", config=config,
                                      args=(1,), callobj=isinstance)
        assert f1 == f1_b
        assert not f1 != f1_b

    def test_function_equality_with_callspec(self, testdir, tmpdir):
        config = testdir.reparseconfig()
        class callspec1:
            param = 1
            funcargs = {}
            id = "hello"
        class callspec2:
            param = 1
            funcargs = {}
            id = "world"
        collection = object()
        f5 = py.test.collect.Function(name="name", config=config,
            callspec=callspec1, callobj=isinstance, collection=collection)
        f5b = py.test.collect.Function(name="name", config=config,
            callspec=callspec2, callobj=isinstance, collection=collection)
        assert f5 != f5b
        assert not (f5 == f5b)

    def test_pyfunc_call(self, testdir):
        item = testdir.getitem("def test_func(): raise ValueError")
        config = item.config
        class MyPlugin1:
            def pytest_pyfunc_call(self, pyfuncitem):
                raise ValueError
        class MyPlugin2:
            def pytest_pyfunc_call(self, pyfuncitem):
                return True
        config.pluginmanager.register(MyPlugin1())
        config.pluginmanager.register(MyPlugin2())
        config.hook.pytest_pyfunc_call(pyfuncitem=item)

class TestSorting:
    def test_check_equality(self, testdir):
        modcol = testdir.getmodulecol("""
            def test_pass(): pass
            def test_fail(): assert 0
        """)
        fn1 = modcol.collect_by_name("test_pass")
        assert isinstance(fn1, py.test.collect.Function)
        fn2 = modcol.collect_by_name("test_pass")
        assert isinstance(fn2, py.test.collect.Function)

        assert fn1 == fn2
        assert fn1 != modcol
        if py.std.sys.version_info < (3, 0):
            assert cmp(fn1, fn2) == 0
        assert hash(fn1) == hash(fn2)

        fn3 = modcol.collect_by_name("test_fail")
        assert isinstance(fn3, py.test.collect.Function)
        assert not (fn1 == fn3)
        assert fn1 != fn3

        for fn in fn1,fn2,fn3:
            assert fn != 3
            assert fn != modcol
            assert fn != [1,2,3]
            assert [1,2,3] != fn
            assert modcol != fn

    def test_allow_sane_sorting_for_decorators(self, testdir):
        modcol = testdir.getmodulecol("""
            def dec(f):
                g = lambda: f(2)
                g.place_as = f
                return g


            def test_b(y):
                pass
            test_b = dec(test_b)

            def test_a(y):
                pass
            test_a = dec(test_a)
        """)
        colitems = modcol.collect()
        assert len(colitems) == 2
        assert [item.name for item in colitems] == ['test_b', 'test_a']


class TestConftestCustomization:
    def test_pytest_pycollect_module(self, testdir):
        testdir.makeconftest("""
            import py
            class MyModule(py.test.collect.Module):
                pass
            def pytest_pycollect_makemodule(path, parent):
                if path.basename == "test_xyz.py":
                    return MyModule(path, parent)
        """)
        testdir.makepyfile("def some(): pass")
        testdir.makepyfile(test_xyz="")
        result = testdir.runpytest("--collectonly")
        result.stdout.fnmatch_lines([
            "*<Module*test_pytest*",
            "*<MyModule*xyz*",
        ])

    def test_pytest_pycollect_makeitem(self, testdir):
        testdir.makeconftest("""
            import py
            class MyFunction(py.test.collect.Function):
                pass
            def pytest_pycollect_makeitem(collector, name, obj):
                if name == "some":
                    return MyFunction(name, collector)
        """)
        testdir.makepyfile("def some(): pass")
        result = testdir.runpytest("--collectonly")
        result.stdout.fnmatch_lines([
            "*MyFunction*some*",
        ])

    def test_makeitem_non_underscore(self, testdir, monkeypatch):
        modcol = testdir.getmodulecol("def _hello(): pass")
        l = []
        monkeypatch.setattr(py.test.collect.Module, 'makeitem',
            lambda self, name, obj: l.append(name))
        l = modcol.collect()
        assert '_hello' not in l

def test_setup_only_available_in_subdir(testdir):
    sub1 = testdir.mkpydir("sub1")
    sub2 = testdir.mkpydir("sub2")
    sub1.join("conftest.py").write(py.code.Source("""
        import py
        def pytest_runtest_setup(item):
            assert item.fspath.purebasename == "test_in_sub1"
        def pytest_runtest_call(item):
            assert item.fspath.purebasename == "test_in_sub1"
        def pytest_runtest_teardown(item):
            assert item.fspath.purebasename == "test_in_sub1"
    """))
    sub2.join("conftest.py").write(py.code.Source("""
        import py
        def pytest_runtest_setup(item):
            assert item.fspath.purebasename == "test_in_sub2"
        def pytest_runtest_call(item):
            assert item.fspath.purebasename == "test_in_sub2"
        def pytest_runtest_teardown(item):
            assert item.fspath.purebasename == "test_in_sub2"
    """))
    sub1.join("test_in_sub1.py").write("def test_1(): pass")
    sub2.join("test_in_sub2.py").write("def test_2(): pass")
    result = testdir.runpytest("-v", "-s")
    result.stdout.fnmatch_lines([
        "*2 passed*"
    ])

def test_generate_tests_only_done_in_subdir(testdir):
    sub1 = testdir.mkpydir("sub1")
    sub2 = testdir.mkpydir("sub2")
    sub1.join("conftest.py").write(py.code.Source("""
        def pytest_generate_tests(metafunc):
            assert metafunc.function.__name__ == "test_1"
    """))
    sub2.join("conftest.py").write(py.code.Source("""
        def pytest_generate_tests(metafunc):
            assert metafunc.function.__name__ == "test_2"
    """))
    sub1.join("test_in_sub1.py").write("def test_1(): pass")
    sub2.join("test_in_sub2.py").write("def test_2(): pass")
    result = testdir.runpytest("-v", "-s", sub1, sub2, sub1)
    result.stdout.fnmatch_lines([
        "*3 passed*"
    ])

def test_modulecol_roundtrip(testdir):
    modcol = testdir.getmodulecol("pass", withinit=True)
    trail = modcol.collection.getid(modcol)
    newcol = modcol.collection.getbyid(trail)[0]
    assert modcol.name == newcol.name


class TestTracebackCutting:
    def test_skip_simple(self):
        excinfo = py.test.raises(py.test.skip.Exception, 'py.test.skip("xxx")')
        assert excinfo.traceback[-1].frame.code.name == "skip"
        assert excinfo.traceback[-1].ishidden()

    def test_traceback_argsetup(self, testdir):
        testdir.makeconftest("""
            def pytest_funcarg__hello(request):
                raise ValueError("xyz")
        """)
        p = testdir.makepyfile("def test(hello): pass")
        result = testdir.runpytest(p)
        assert result.ret != 0
        out = result.stdout.str()
        assert out.find("xyz") != -1
        assert out.find("conftest.py:2: ValueError") != -1
        numentries = out.count("_ _ _") # separator for traceback entries
        assert numentries == 0

        result = testdir.runpytest("--fulltrace", p)
        out = result.stdout.str()
        assert out.find("conftest.py:2: ValueError") != -1
        numentries = out.count("_ _ _ _") # separator for traceback entries
        assert numentries >3

    def test_traceback_error_during_import(self, testdir):
        testdir.makepyfile("""
            x = 1
            x = 2
            x = 17
            asd
        """)
        result = testdir.runpytest()
        assert result.ret != 0
        out = result.stdout.str()
        assert "x = 1" not in out
        assert "x = 2" not in out
        result.stdout.fnmatch_lines([
            ">*asd*",
            "E*NameError*",
        ])
        result = testdir.runpytest("--fulltrace")
        out = result.stdout.str()
        assert "x = 1" in out
        assert "x = 2" in out
        result.stdout.fnmatch_lines([
            ">*asd*",
            "E*NameError*",
        ])

def test_getfuncargnames():
    def f(): pass
    assert not funcargs.getfuncargnames(f)
    def g(arg): pass
    assert funcargs.getfuncargnames(g) == ['arg']
    def h(arg1, arg2="hello"): pass
    assert funcargs.getfuncargnames(h) == ['arg1']
    def h(arg1, arg2, arg3="hello"): pass
    assert funcargs.getfuncargnames(h) == ['arg1', 'arg2']
    class A:
        def f(self, arg1, arg2="hello"):
            pass
    assert funcargs.getfuncargnames(A().f) == ['arg1']
    if sys.version_info < (3,0):
        assert funcargs.getfuncargnames(A.f) == ['arg1']

def test_callspec_repr():
    cs = funcargs.CallSpec({}, 'hello', 1)
    repr(cs)
    cs = funcargs.CallSpec({}, 'hello', funcargs._notexists)
    repr(cs)

class TestFillFuncArgs:
    def test_funcarg_lookupfails(self, testdir):
        testdir.makeconftest("""
            def pytest_funcarg__xyzsomething(request):
                return 42
        """)
        item = testdir.getitem("def test_func(some): pass")
        exc = py.test.raises(funcargs.FuncargRequest.LookupError,
            "funcargs.fillfuncargs(item)")
        s = str(exc.value)
        assert s.find("xyzsomething") != -1

    def test_funcarg_lookup_default(self, testdir):
        item = testdir.getitem("def test_func(some, other=42): pass")
        class Provider:
            def pytest_funcarg__some(self, request):
                return request.function.__name__
        item.config.pluginmanager.register(Provider())
        funcargs.fillfuncargs(item)
        assert len(item.funcargs) == 1

    def test_funcarg_basic(self, testdir):
        item = testdir.getitem("def test_func(some, other): pass")
        class Provider:
            def pytest_funcarg__some(self, request):
                return request.function.__name__
            def pytest_funcarg__other(self, request):
                return 42
        item.config.pluginmanager.register(Provider())
        funcargs.fillfuncargs(item)
        assert len(item.funcargs) == 2
        assert item.funcargs['some'] == "test_func"
        assert item.funcargs['other'] == 42

    def test_funcarg_lookup_modulelevel(self, testdir):
        modcol = testdir.getmodulecol("""
            def pytest_funcarg__something(request):
                return request.function.__name__

            class TestClass:
                def test_method(self, something):
                    pass
            def test_func(something):
                pass
        """)
        item1, item2 = testdir.genitems([modcol])
        funcargs.fillfuncargs(item1)
        assert item1.funcargs['something'] ==  "test_method"
        funcargs.fillfuncargs(item2)
        assert item2.funcargs['something'] ==  "test_func"

    def test_funcarg_lookup_classlevel(self, testdir):
        p = testdir.makepyfile("""
            class TestClass:
                def pytest_funcarg__something(self, request):
                    return request.instance
                def test_method(self, something):
                    assert something is self
        """)
        result = testdir.runpytest(p)
        result.stdout.fnmatch_lines([
            "*1 passed*"
        ])

    def test_fillfuncargs_exposed(self, testdir):
        item = testdir.getitem("def test_func(some, other=42): pass")
        class Provider:
            def pytest_funcarg__some(self, request):
                return request.function.__name__
        item.config.pluginmanager.register(Provider())
        if hasattr(item, '_args'):
            del item._args
        py.test.collect._fillfuncargs(item)
        assert len(item.funcargs) == 1

class TestRequest:
    def test_request_attributes(self, testdir):
        item = testdir.getitem("""
            def pytest_funcarg__something(request): pass
            def test_func(something): pass
        """)
        req = funcargs.FuncargRequest(item)
        assert req.function == item.obj
        assert hasattr(req.module, 'test_func')
        assert req.cls is None
        assert req.function.__name__ == "test_func"
        assert req.config == item.config
        assert repr(req).find(req.function.__name__) != -1

    def test_request_attributes_method(self, testdir):
        item, = testdir.getitems("""
            class TestB:
                def test_func(self, something):
                    pass
        """)
        req = funcargs.FuncargRequest(item)
        assert req.cls.__name__ == "TestB"
        assert req.instance.__class__ == req.cls

    def XXXtest_request_contains_funcarg_name2factory(self, testdir):
        modcol = testdir.getmodulecol("""
            def pytest_funcarg__something(request):
                pass
            class TestClass:
                def test_method(self, something):
                    pass
        """)
        item1, = testdir.genitems([modcol])
        assert item1.name == "test_method"
        name2factory = funcargs.FuncargRequest(item1)._name2factory
        assert len(name2factory) == 1
        assert name2factory[0].__name__ == "pytest_funcarg__something"

    def test_getfuncargvalue_recursive(self, testdir):
        testdir.makeconftest("""
            def pytest_funcarg__something(request):
                return 1
        """)
        item = testdir.getitem("""
            def pytest_funcarg__something(request):
                return request.getfuncargvalue("something") + 1
            def test_func(something):
                assert something == 2
        """)
        req = funcargs.FuncargRequest(item)
        val = req.getfuncargvalue("something")
        assert val == 2

    def test_getfuncargvalue(self, testdir):
        item = testdir.getitem("""
            l = [2]
            def pytest_funcarg__something(request): return 1
            def pytest_funcarg__other(request):
                return l.pop()
            def test_func(something): pass
        """)
        req = funcargs.FuncargRequest(item)
        py.test.raises(req.LookupError, req.getfuncargvalue, "notexists")
        val = req.getfuncargvalue("something")
        assert val == 1
        val = req.getfuncargvalue("something")
        assert val == 1
        val2 = req.getfuncargvalue("other")
        assert val2 == 2
        val2 = req.getfuncargvalue("other")  # see about caching
        assert val2 == 2
        req._fillfuncargs()
        assert item.funcargs == {'something': 1}

    def test_request_addfinalizer(self, testdir):
        item = testdir.getitem("""
            teardownlist = []
            def pytest_funcarg__something(request):
                request.addfinalizer(lambda: teardownlist.append(1))
            def test_func(something): pass
        """)
        req = funcargs.FuncargRequest(item)
        req.config._setupstate.prepare(item) # XXX
        req._fillfuncargs()
        # successively check finalization calls
        teardownlist = item.getparent(py.test.collect.Module).obj.teardownlist
        ss = item.config._setupstate
        assert not teardownlist
        ss.teardown_exact(item)
        print(ss.stack)
        assert teardownlist == [1]

    def test_request_addfinalizer_partial_setup_failure(self, testdir):
        p = testdir.makepyfile("""
            l = []
            def pytest_funcarg__something(request):
                request.addfinalizer(lambda: l.append(None))
            def test_func(something, missingarg):
                pass
            def test_second():
                assert len(l) == 1
        """)
        result = testdir.runpytest(p)
        result.stdout.fnmatch_lines([
            "*1 passed*1 error*"
            ])

    def test_request_getmodulepath(self, testdir):
        modcol = testdir.getmodulecol("def test_somefunc(): pass")
        item, = testdir.genitems([modcol])
        req = funcargs.FuncargRequest(item)
        assert req.fspath == modcol.fspath

def test_applymarker(testdir):
    item1,item2 = testdir.getitems("""
        class TestClass:
            def test_func1(self, something):
                pass
            def test_func2(self, something):
                pass
    """)
    req1 = funcargs.FuncargRequest(item1)
    assert 'xfail' not in item1.keywords
    req1.applymarker(py.test.mark.xfail)
    assert 'xfail' in item1.keywords
    assert 'skipif' not in item1.keywords
    req1.applymarker(py.test.mark.skipif)
    assert 'skipif' in item1.keywords
    py.test.raises(ValueError, "req1.applymarker(42)")

class TestRequestCachedSetup:
    def test_request_cachedsetup(self, testdir):
        item1,item2 = testdir.getitems("""
            class TestClass:
                def test_func1(self, something):
                    pass
                def test_func2(self, something):
                    pass
        """)
        req1 = funcargs.FuncargRequest(item1)
        l = ["hello"]
        def setup():
            return l.pop()
        ret1 = req1.cached_setup(setup)
        assert ret1 == "hello"
        ret1b = req1.cached_setup(setup)
        assert ret1 == ret1b
        req2 = funcargs.FuncargRequest(item2)
        ret2 = req2.cached_setup(setup)
        assert ret2 == ret1

    def test_request_cachedsetup_extrakey(self, testdir):
        item1 = testdir.getitem("def test_func(): pass")
        req1 = funcargs.FuncargRequest(item1)
        l = ["hello", "world"]
        def setup():
            return l.pop()
        ret1 = req1.cached_setup(setup, extrakey=1)
        ret2 = req1.cached_setup(setup, extrakey=2)
        assert ret2 == "hello"
        assert ret1 == "world"
        ret1b = req1.cached_setup(setup, extrakey=1)
        ret2b = req1.cached_setup(setup, extrakey=2)
        assert ret1 == ret1b
        assert ret2 == ret2b

    def test_request_cachedsetup_cache_deletion(self, testdir):
        item1 = testdir.getitem("def test_func(): pass")
        req1 = funcargs.FuncargRequest(item1)
        l = []
        def setup():
            l.append("setup")
        def teardown(val):
            l.append("teardown")
        ret1 = req1.cached_setup(setup, teardown, scope="function")
        assert l == ['setup']
        # artificial call of finalizer
        req1.config._setupstate._callfinalizers(item1)
        assert l == ["setup", "teardown"]
        ret2 = req1.cached_setup(setup, teardown, scope="function")
        assert l == ["setup", "teardown", "setup"]
        req1.config._setupstate._callfinalizers(item1)
        assert l == ["setup", "teardown", "setup", "teardown"]

    def test_request_cached_setup_two_args(self, testdir):
        testdir.makepyfile("""
            def pytest_funcarg__arg1(request):
                return request.cached_setup(lambda: 42)
            def pytest_funcarg__arg2(request):
                return request.cached_setup(lambda: 17)
            def test_two_different_setups(arg1, arg2):
                assert arg1 != arg2
        """)
        result = testdir.runpytest("-v")
        result.stdout.fnmatch_lines([
            "*1 passed*"
        ])

    def test_request_cached_setup_getfuncargvalue(self, testdir):
        testdir.makepyfile("""
            def pytest_funcarg__arg1(request):
                arg1 = request.getfuncargvalue("arg2")
                return request.cached_setup(lambda: arg1 + 1)
            def pytest_funcarg__arg2(request):
                return request.cached_setup(lambda: 10)
            def test_two_funcarg(arg1):
                assert arg1 == 11
        """)
        result = testdir.runpytest("-v")
        result.stdout.fnmatch_lines([
            "*1 passed*"
        ])

    def test_request_cached_setup_functional(self, testdir):
        testdir.makepyfile(test_0="""
            l = []
            def pytest_funcarg__something(request):
                val = request.cached_setup(fsetup, fteardown)
                return val
            def fsetup(mycache=[1]):
                l.append(mycache.pop())
                return l
            def fteardown(something):
                l.remove(something[0])
                l.append(2)
            def test_list_once(something):
                assert something == [1]
            def test_list_twice(something):
                assert something == [1]
        """)
        testdir.makepyfile(test_1="""
            import test_0 # should have run already
            def test_check_test0_has_teardown_correct():
                assert test_0.l == [2]
        """)
        result = testdir.runpytest("-v")
        result.stdout.fnmatch_lines([
            "*3 passed*"
        ])

class TestMetafunc:
    def test_no_funcargs(self, testdir):
        def function(): pass
        metafunc = funcargs.Metafunc(function)
        assert not metafunc.funcargnames

    def test_function_basic(self):
        def func(arg1, arg2="qwe"): pass
        metafunc = funcargs.Metafunc(func)
        assert len(metafunc.funcargnames) == 1
        assert 'arg1' in metafunc.funcargnames
        assert metafunc.function is func
        assert metafunc.cls is None

    def test_addcall_no_args(self):
        def func(arg1): pass
        metafunc = funcargs.Metafunc(func)
        metafunc.addcall()
        assert len(metafunc._calls) == 1
        call = metafunc._calls[0]
        assert call.id == "0"
        assert not hasattr(call, 'param')

    def test_addcall_id(self):
        def func(arg1): pass
        metafunc = funcargs.Metafunc(func)
        py.test.raises(ValueError, "metafunc.addcall(id=None)")

        metafunc.addcall(id=1)
        py.test.raises(ValueError, "metafunc.addcall(id=1)")
        py.test.raises(ValueError, "metafunc.addcall(id='1')")
        metafunc.addcall(id=2)
        assert len(metafunc._calls) == 2
        assert metafunc._calls[0].id == "1"
        assert metafunc._calls[1].id == "2"

    def test_addcall_param(self):
        def func(arg1): pass
        metafunc = funcargs.Metafunc(func)
        class obj: pass
        metafunc.addcall(param=obj)
        metafunc.addcall(param=obj)
        metafunc.addcall(param=1)
        assert len(metafunc._calls) == 3
        assert metafunc._calls[0].param == obj
        assert metafunc._calls[1].param == obj
        assert metafunc._calls[2].param == 1

    def test_addcall_funcargs(self):
        def func(arg1): pass
        metafunc = funcargs.Metafunc(func)
        class obj: pass
        metafunc.addcall(funcargs={"x": 2})
        metafunc.addcall(funcargs={"x": 3})
        assert len(metafunc._calls) == 2
        assert metafunc._calls[0].funcargs == {'x': 2}
        assert metafunc._calls[1].funcargs == {'x': 3}
        assert not hasattr(metafunc._calls[1], 'param')

class TestGenfuncFunctional:
    def test_attributes(self, testdir):
        p = testdir.makepyfile("""
            # assumes that generate/provide runs in the same process
            import py
            def pytest_generate_tests(metafunc):
                metafunc.addcall(param=metafunc)

            def pytest_funcarg__metafunc(request):
                assert request._pyfuncitem._genid == "0"
                return request.param

            def test_function(metafunc, pytestconfig):
                assert metafunc.config == pytestconfig
                assert metafunc.module.__name__ == __name__
                assert metafunc.function == test_function
                assert metafunc.cls is None

            class TestClass:
                def test_method(self, metafunc, pytestconfig):
                    assert metafunc.config == pytestconfig
                    assert metafunc.module.__name__ == __name__
                    if py.std.sys.version_info > (3, 0):
                        unbound = TestClass.test_method
                    else:
                        unbound = TestClass.test_method.im_func
                    # XXX actually have an unbound test function here?
                    assert metafunc.function == unbound
                    assert metafunc.cls == TestClass
        """)
        result = testdir.runpytest(p, "-v")
        result.stdout.fnmatch_lines([
            "*2 passed in*",
        ])

    def test_addcall_with_two_funcargs_generators(self, testdir):
        testdir.makeconftest("""
            def pytest_generate_tests(metafunc):
                assert "arg1" in metafunc.funcargnames
                metafunc.addcall(funcargs=dict(arg1=1, arg2=2))
        """)
        p = testdir.makepyfile("""
            def pytest_generate_tests(metafunc):
                metafunc.addcall(funcargs=dict(arg1=1, arg2=1))

            class TestClass:
                def test_myfunc(self, arg1, arg2):
                    assert arg1 == arg2
        """)
        result = testdir.runpytest("-v", p)
        result.stdout.fnmatch_lines([
            "*test_myfunc*0*PASS*",
            "*test_myfunc*1*FAIL*",
            "*1 failed, 1 passed*"
        ])

    def test_two_functions(self, testdir):
        p = testdir.makepyfile("""
            def pytest_generate_tests(metafunc):
                metafunc.addcall(param=10)
                metafunc.addcall(param=20)

            def pytest_funcarg__arg1(request):
                return request.param

            def test_func1(arg1):
                assert arg1 == 10
            def test_func2(arg1):
                assert arg1 in (10, 20)
        """)
        result = testdir.runpytest("-v", p)
        result.stdout.fnmatch_lines([
            "*test_func1*0*PASS*",
            "*test_func1*1*FAIL*",
            "*test_func2*PASS*",
            "*1 failed, 3 passed*"
        ])

    def test_generate_plugin_and_module(self, testdir):
        testdir.makeconftest("""
            def pytest_generate_tests(metafunc):
                assert "arg1" in metafunc.funcargnames
                metafunc.addcall(id="world", param=(2,100))
        """)
        p = testdir.makepyfile("""
            def pytest_generate_tests(metafunc):
                metafunc.addcall(param=(1,1), id="hello")

            def pytest_funcarg__arg1(request):
                return request.param[0]
            def pytest_funcarg__arg2(request):
                return request.param[1]

            class TestClass:
                def test_myfunc(self, arg1, arg2):
                    assert arg1 == arg2
        """)
        result = testdir.runpytest("-v", p)
        result.stdout.fnmatch_lines([
            "*test_myfunc*hello*PASS*",
            "*test_myfunc*world*FAIL*",
            "*1 failed, 1 passed*"
        ])

    def test_generate_tests_in_class(self, testdir):
        p = testdir.makepyfile("""
            class TestClass:
                def pytest_generate_tests(self, metafunc):
                    metafunc.addcall(funcargs={'hello': 'world'}, id="hello")

                def test_myfunc(self, hello):
                    assert hello == "world"
        """)
        result = testdir.runpytest("-v", p)
        result.stdout.fnmatch_lines([
            "*test_myfunc*hello*PASS*",
            "*1 passed*"
        ])

    def test_two_functions_not_same_instance(self, testdir):
        p = testdir.makepyfile("""
            def pytest_generate_tests(metafunc):
                metafunc.addcall({'arg1': 10})
                metafunc.addcall({'arg1': 20})

            class TestClass:
                def test_func(self, arg1):
                    assert not hasattr(self, 'x')
                    self.x = 1
        """)
        result = testdir.runpytest("-v", p)
        result.stdout.fnmatch_lines([
            "*test_func*0*PASS*",
            "*test_func*1*PASS*",
            "*2 pass*",
        ])


def test_conftest_funcargs_only_available_in_subdir(testdir):
    sub1 = testdir.mkpydir("sub1")
    sub2 = testdir.mkpydir("sub2")
    sub1.join("conftest.py").write(py.code.Source("""
        import py
        def pytest_funcarg__arg1(request):
            py.test.raises(Exception, "request.getfuncargvalue('arg2')")
    """))
    sub2.join("conftest.py").write(py.code.Source("""
        import py
        def pytest_funcarg__arg2(request):
            py.test.raises(Exception, "request.getfuncargvalue('arg1')")
    """))

    sub1.join("test_in_sub1.py").write("def test_1(arg1): pass")
    sub2.join("test_in_sub2.py").write("def test_2(arg2): pass")
    result = testdir.runpytest("-v")
    result.stdout.fnmatch_lines([
        "*2 passed*"
    ])

def test_funcarg_non_pycollectobj(testdir): # rough jstests usage
    testdir.makeconftest("""
        import py
        def pytest_pycollect_makeitem(collector, name, obj):
            if name == "MyClass":
                return MyCollector(name, parent=collector)
        class MyCollector(py.test.collect.Collector):
            def reportinfo(self):
                return self.fspath, 3, "xyz"
    """)
    modcol = testdir.getmodulecol("""
        def pytest_funcarg__arg1(request):
            return 42
        class MyClass:
            pass
    """)
    clscol = modcol.collect()[0]
    clscol.obj = lambda arg1: None
    clscol.funcargs = {}
    funcargs.fillfuncargs(clscol)
    assert clscol.funcargs['arg1'] == 42


def test_funcarg_lookup_error(testdir):
    p = testdir.makepyfile("""
        def test_lookup_error(unknown):
            pass
    """)
    result = testdir.runpytest()
    result.stdout.fnmatch_lines([
        "*ERROR at setup of test_lookup_error*",
        "*def test_lookup_error(unknown):*",
        "*LookupError: no factory found*unknown*",
        "*available funcargs*",
        "*1 error*",
    ])
    assert "INTERNAL" not in result.stdout.str()

class TestReportInfo:
    def test_itemreport_reportinfo(self, testdir, linecomp):
        testdir.makeconftest("""
            import py
            class Function(py.test.collect.Function):
                def reportinfo(self):
                    return "ABCDE", 42, "custom"
        """)
        item = testdir.getitem("def test_func(): pass")
        runner = item.config.pluginmanager.getplugin("runner")
        nodeinfo = runner.getitemnodeinfo(item)
        assert nodeinfo.location == ("ABCDE", 42, "custom")

    def test_itemreport_pytest_report_iteminfo(self, testdir, linecomp):
        item = testdir.getitem("def test_func(): pass")
        tup = "FGHJ", 42, "custom"
        class Plugin:
            def pytest_report_iteminfo(self, item):
                return tup
        item.config.pluginmanager.register(Plugin())
        runner = runner = item.config.pluginmanager.getplugin("runner")
        nodeinfo = runner.getitemnodeinfo(item)
        location = nodeinfo.location
        assert location == tup

    def test_func_reportinfo(self, testdir):
        item = testdir.getitem("def test_func(): pass")
        fspath, lineno, modpath = item.reportinfo()
        assert fspath == item.fspath
        assert lineno == 0
        assert modpath == "test_func"

    def test_class_reportinfo(self, testdir):
        modcol = testdir.getmodulecol("""
            # lineno 0
            class TestClass:
                def test_hello(self): pass
        """)
        classcol = modcol.collect_by_name("TestClass")
        fspath, lineno, msg = classcol.reportinfo()
        assert fspath == modcol.fspath
        assert lineno == 1
        assert msg == "TestClass"

    def test_generator_reportinfo(self, testdir):
        modcol = testdir.getmodulecol("""
            # lineno 0
            def test_gen():
                def check(x):
                    assert x
                yield check, 3
        """)
        gencol = modcol.collect_by_name("test_gen")
        fspath, lineno, modpath = gencol.reportinfo()
        assert fspath == modcol.fspath
        assert lineno == 1
        assert modpath == "test_gen"

        genitem = gencol.collect()[0]
        fspath, lineno, modpath = genitem.reportinfo()
        assert fspath == modcol.fspath
        assert lineno == 2
        assert modpath == "test_gen[0]"
        """
            def test_func():
                pass
            def test_genfunc():
                def check(x):
                    pass
                yield check, 3
            class TestClass:
                def test_method(self):
                    pass
       """

def test_show_funcarg(testdir):
    result = testdir.runpytest("--funcargs")
    result.stdout.fnmatch_lines([
            "*tmpdir*",
            "*temporary directory*",
        ]
    )