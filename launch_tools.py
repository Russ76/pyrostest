"""Utilities for launching ros nodes for tests.
"""
import functools
import time
import roslaunch
import rosnode


class ROSLauncher(roslaunch.scriptapi.ROSLaunch):
    """
    ROSLaunch but allows the use of launch files.

    This was found by peering into the roslaunch util source code from
    `which roslaunch`.
    """
    def __init__(self, files):
        super().__init__()
        uuid = roslaunch.rlutil.get_or_generate_uuid(None, True)
        self.parent = roslaunch.parent.ROSLaunchParent(uuid,
                files, is_core=False)

# TODO(joshuamorton@gatech.edu): swap this to a Map[int, launcher], where the
# int is incrementally generated and stored within the calling decorator. This
# will prevent the issue of overwriting or cross writing if it becomes a
# danger.
_LAUNCHER = None

def with_launch_file(package, launch):
    """Decorator to source a launch file for running nodes.

    This should always be run first.

    This and launch nodes work together gracefully, but this poses a danger.
    Because they rely on a global variable, multiple running simultaneously
    (in the same thread) can cause issues by overwriting the 'launcher'
    value. This could be fixed if needed, but I don't think it will be an
    issue.
    """
    full_name = roslaunch.rlutil.resolve_launch_arguments([package, launch])
    def launcher(func):
        """Decorator function created by the decorator-gen.
        """
        @functools.wraps(func)
        def new_test(self):
            """Wrapper around the user provided test that runs a launch file.
            """
            launch = ROSLauncher(full_name)
            launch.start()
            global _LAUNCHER # pylint: disable=global-statement
            _LAUNCHER = launch

            temp = func(self)
            _launcher = None
            return temp
        return new_test
    return launcher

def launch_node(package, name, namespace=None):
    """Decorator to manage running a node and shutting it down gracefully.

    Note that this will wrap itself up cleanly and launch all nodes with a
    single launcher, instead of multiples.
    """
    if not namespace:
        namespace = '/'+package
    def launcher(func):
        """Actual decorator generated by the above.
        """
        @functools.wraps(func)
        def new_test(self):
            """Wrapper around the user-provided test that runs a ros node.
            """
            node = roslaunch.core.Node(package, name, namespace=namespace)
            is_master = False
            global _LAUNCHER # pylint: disable=global-statement
            if _LAUNCHER is None:
                launch = roslaunch.scriptapi.ROSLaunch()
                launch.start()
                _LAUNCHER = launch
                is_master = True
            else:
                launch = _LAUNCHER

            process = launch.launch(node)
            # Beware this is a bit of a hack, and will currently not work if we
            # want to run more than 1 node with the same name.
            while not any(nn.split('/')[-1].startswith(name.replace('.', '_'))
                    for nn in rosnode.get_node_names()):
                time.sleep(.1)
            try:
                temp = func(self)
            except:
                raise
            finally:
                process.stop()
            if is_master:
                _launcher = None
            return temp

        return new_test
    return launcher


