from __future__ import unicode_literals
import sys
import os

import pytest
from docopt import DocoptExit
from scripttest import TestFileEnvironment as FileEnvironment

import konch


try:
    import ptpython  # noqa: F401
except ImportError:
    HAS_PTPYTHON = False
else:
    HAS_PTPYTHON = True


def assert_in_output(s, res, message=None):
    """Assert that a string is in either stdout or std err.
    Included because banners are sometimes outputted to stderr.
    """
    assert any([s in res.stdout, s in res.stderr]), message or f"{s} not in output"


@pytest.fixture
def env():
    env_ = FileEnvironment(ignore_hidden=False)
    env_.environ["KONCH_AUTH_FILE"] = os.path.join(env_.base_path, "konch_auth")
    return env_


def teardown_function(func):
    konch.reset_config()


def test_make_banner_custom():
    text = "I want to be the very best"
    result = konch.make_banner(text)
    assert text in result
    assert sys.version in result


def test_full_formatter():
    class Foo:
        def __repr__(self):
            return "<Foo>"

    context = {"foo": Foo(), "bar": 42}

    assert (
        konch.format_context(context, formatter="full")
        == "\nContext:\nbar: 42\nfoo: <Foo>"
    )


def test_short_formatter():
    class Foo:
        def __repr__(self):
            return "<Foo>"

    context = {"foo": Foo(), "bar": 42}

    assert konch.format_context(context, formatter="short") == "\nContext:\nbar, foo"


def test_custom_formatter():
    context = {"foo": 42, "bar": 24}

    def my_formatter(ctx):
        return "*".join(sorted(ctx.keys()))

    assert konch.format_context(context, formatter=my_formatter) == "bar*foo"


def test_make_banner_includes_full_context_by_default():
    context = {"foo": 42}
    result = konch.make_banner(context=context)
    assert konch.format_context(context, formatter="full") in result


def test_make_banner_hide_context():
    context = {"foo": 42}
    result = konch.make_banner(context=context, context_format="hide")
    assert konch.format_context(context) not in result


def test_make_banner_custom_format():
    context = {"foo": 42}
    result = konch.make_banner(context=context, context_format=lambda ctx: repr(ctx))
    assert repr(context) in result


def test_cfg_defaults():
    assert konch._cfg["shell"] == konch.AutoShell
    assert konch._cfg["banner"] is None
    assert konch._cfg["context"] == {}
    assert konch._cfg["context_format"] == "full"


def test_config():
    assert konch._cfg == konch.Config()
    konch.config({"banner": "Foo bar"})
    assert konch._cfg["banner"] == "Foo bar"


def test_reset_config():
    assert konch._cfg == konch.Config()
    konch.config({"banner": "Foo bar"})
    konch.reset_config()
    assert konch._cfg == konch.Config()


def test_parse_args():
    try:
        args = konch.parse_args()
        assert "--shell" in args
        assert "init" in args
        assert "<config_file>" in args
        assert "--name" in args
    except DocoptExit:
        pass


def test_context_list2dict():
    import math

    class MyClass:
        pass

    def my_func():
        pass

    my_objects = [math, MyClass, my_func]
    expected = {"my_func": my_func, "MyClass": MyClass, "math": math}
    assert konch.context_list2dict(my_objects) == expected


def test_config_list():
    assert konch._cfg == konch.Config()

    def my_func():
        return

    konch.config({"context": [my_func]})
    assert konch._cfg["context"]["my_func"] == my_func


def test_config_converts_list_context():
    import math

    config = konch.Config(context=[math])
    assert config["context"] == {"math": math}


def test_config_set_context_converts_list():
    import math

    config = konch.Config()
    config["context"] = [math]
    assert config["context"] == {"math": math}


def test_config_update_context_converts_list():
    import math

    config = konch.Config()
    config.update({"context": [math]})
    assert config["context"] == {"math": math}


def test_named_config_adds_to_registry():
    assert konch._config_registry["default"] == konch._cfg
    assert len(konch._config_registry.keys()) == 1
    konch.named_config("mynamespace", {"context": {"foo": 42}})
    assert len(konch._config_registry.keys()) == 2
    # reset config_registry
    konch._config_registry = {"default": konch._cfg}


def test_context_can_be_callable():
    def get_context():
        return {"foo": 42}

    shell = konch.Shell(context=get_context)

    assert shell.context == {"foo": 42}


##### Command tests #####


def test_init_creates_config_file(env):
    res = env.run("konch", "init")
    assert res.returncode == 0
    assert konch.CONFIG_FILE in res.files_created


def test_init_with_filename(env):
    res = env.run("konch", "init", "myconfig")
    assert "myconfig" in res.files_created


def test_konch_init_when_config_file_exists(env):
    env.run("konch", "init")
    res = env.run("konch", "init", expect_error=True)
    assert "already exists" in res.stderr
    assert res.returncode == 1


def test_file_blocked(env, request):
    env.writefile(".konchrc", content=b"givemeyourbitcoinz")
    request.addfinalizer(lambda: os.remove(os.path.join(env.base_path, ".konchrc")))
    res = env.run("konch", expect_stderr=True, expect_error=True)
    assert "blocked" in res.stderr
    assert res.returncode == 1


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_allow_file(env, request):
    env.writefile(".konchrc", content=b"import konch")
    request.addfinalizer(lambda: os.remove(os.path.join(env.base_path, ".konchrc")))
    env.run("konch", "allow")
    res = env.run("konch")
    assert res.returncode == 0


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_allow_specified_file(env, request):
    env.writefile("mykonchrc", content=b"import konch")
    request.addfinalizer(lambda: os.remove(os.path.join(env.base_path, "mykonchrc")))

    res = env.run("konch", "-f", "mykonchrc", expect_error=True)
    assert res.returncode == 1

    env.run("konch", "allow", "mykonchrc")
    res = env.run("konch", "-f", "mykonchrc", expect_error=False)
    assert res.returncode == 0


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_allow_file_not_found(env, request):
    res = env.run("konch", "allow", "notfound", expect_stderr=True, expect_error=True)
    assert "does not exist" in res.stderr
    assert res.returncode == 1


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_file_blocked_if_changed(env, request):
    env.writefile(".konchrc", content=b"import konch")
    request.addfinalizer(lambda: os.remove(os.path.join(env.base_path, ".konchrc")))
    env.run("konch", "allow")
    res = env.run("konch")
    assert res.returncode == 0

    env.writefile(".konchrc", content=b"import konch as k")
    res = env.run("konch", expect_stderr=True, expect_error=True)
    assert "changed" in res.stderr
    assert res.returncode == 1


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_deny_file(env, request):
    env.writefile(".konchrc", content=b"import konch")
    request.addfinalizer(lambda: os.remove(os.path.join(env.base_path, ".konchrc")))
    env.run("konch", "allow")
    res = env.run("konch")
    assert res.returncode == 0

    env.run("konch", "deny")
    res = env.run("konch", expect_stderr=True, expect_error=True)
    assert "blocked" in res.stderr
    assert res.returncode == 1


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_deny_file_not_found(env, request):
    res = env.run("konch", "deny", "notfound", expect_stderr=True, expect_error=True)
    assert "does not exist" in res.stderr
    assert res.returncode == 1


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_default_banner(env):
    env.run("konch", "init")
    res = env.run("konch", expect_stderr=True)
    assert_in_output(str(sys.version), res)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_config_file_not_found(env):
    res = env.run("konch", "-f", "notfound", expect_stderr=True, expect_error=True)
    assert '"notfound" not found' in res.stderr
    assert res.returncode == 1


TEST_CONFIG = """
import konch

konch.config({
    'banner': 'Test banner',
    'prompt': 'myprompt >>>'
})
"""


@pytest.fixture
def fileenv(request, env):
    fpath = os.path.join(env.base_path, "testrc")
    with open(fpath, "w") as fp:
        fp.write(TEST_CONFIG)

    env.run("konch", "allow", fpath)
    yield env
    os.remove(fpath)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_custom_banner(fileenv):
    res = fileenv.run("konch", "-f", "testrc", expect_stderr=True)
    assert_in_output("Test banner", res)


# TODO: Get this test working with IPython
def test_custom_prompt(fileenv):
    res = fileenv.run("konch", "-f", "testrc", "-s", "py", expect_stderr=True)
    assert_in_output("myprompt >>>", res)


def test_version(env):
    res = env.run("konch", "--version")
    assert konch.__version__ in res.stdout
    res = env.run("konch", "-v")
    assert konch.__version__ in res.stdout


TEST_CONFIG_WITH_NAMES = """
import konch

konch.config({
    'context': {
        'foo': 42,
    },
    'banner': 'Default'
})

konch.named_config('conf2', {
    'context': {
        'bar': 24
    },
    'banner': 'Conf2'
})

konch.named_config(['conf3', 'c3'], {
    'context': {
        'baz': 424,
    },
    'banner': 'Conf3',
})
"""


TEST_CONFIG_WITH_SETUP_AND_TEARDOWN = """
import konch

def setup():
    print('setup!')

def teardown():
    print('teardown!')
"""


@pytest.fixture
def names_env(request, env):
    fpath = os.path.join(env.base_path, ".konchrc")
    with open(fpath, "w") as fp:
        fp.write(TEST_CONFIG_WITH_NAMES)

    env.run("konch", "allow", fpath)
    yield env
    os.remove(fpath)


@pytest.fixture
def setup_env(request, env):
    fpath = os.path.join(env.base_path, ".konchrc")
    with open(fpath, "w") as fp:
        fp.write(TEST_CONFIG_WITH_SETUP_AND_TEARDOWN)

    env.run("konch", "allow", fpath)
    yield env
    os.remove(fpath)


@pytest.fixture
def folderenv(request, env):
    folder = os.path.abspath(os.path.join(env.base_path, "testdir"))
    os.makedirs(folder)
    yield env
    os.removedirs(folder)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_default_config(names_env):
    res = names_env.run("konch", expect_stderr=True)
    assert_in_output("Default", res)
    assert_in_output("foo", res)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_setup_teardown(setup_env):
    res = setup_env.run("konch", expect_stderr=True)
    assert_in_output("setup!", res)
    assert_in_output("teardown!", res)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_selecting_named_config(names_env):
    res = names_env.run("konch", "-n", "conf2", expect_stderr=True)
    assert_in_output("Conf2", res)
    assert_in_output("bar", res)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_named_config_with_multiple_names(names_env):
    res = names_env.run("konch", "-n", "conf3", expect_stderr=True)
    assert_in_output("Conf3", res)
    assert_in_output("baz", res)

    res = names_env.run("konch", "-n", "c3", expect_stderr=True)
    assert_in_output("Conf3", res)
    assert_in_output("baz", res)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_selecting_name_that_doesnt_exist(names_env):
    res = names_env.run("konch", "-n", "doesntexist", expect_error=True)
    assert res.returncode == 1
    assert "Invalid --name" in res.stderr


def test_resolve_path(folderenv):
    folderenv.run("konch", "init")
    fpath = os.path.abspath(os.path.join(folderenv.base_path, ".konchrc"))
    assert os.path.exists(fpath)
    folder = os.path.abspath(os.path.join(folderenv.base_path, "testdir"))
    os.chdir(folder)
    assert konch.resolve_path(".konchrc") == fpath
