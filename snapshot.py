# Copyright 2015 Michael Rice <michael@michaelrice.org>
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from __future__ import print_function

import atexit

import requests

from pyVim.connect import SmartConnect, SmartConnectNoSSL, Disconnect
from pyVmomi import vim
from pyVim.task import WaitForTask

from tools import cli

requests.packages.urllib3.disable_warnings()


def setup_args():
    parser = cli.build_arg_parser()
    parser.add_argument('--stack-name', required=True,
                        help="stack name")
    parser.add_argument('-d', '--description', required=False,
                        help="Description for the snapshot")
    parser.add_argument('-n', '--name', required=True,
                        help="Name for the Snapshot")
    my_args = parser.parse_args()
    return cli.prompt_for_password(my_args)

def get_vms(si):
    content = si.RetrieveContent()

    container = content.rootFolder  # starting point to look into
    viewType = [vim.VirtualMachine]  # object types to look for
    recursive = True  # whether we should look into it recursively
    containerView = content.viewManager.CreateContainerView(container, viewType, recursive)


    children = containerView.view
    for child in children:
        yield child

args = setup_args()
si = None
instance_search = False
try:
    si = SmartConnectNoSSL(host=args.host,
                               user=args.user,
                               pwd=args.password)
    atexit.register(Disconnect, si)
except IOError:
    pass

if not si:
    raise SystemExit("Unable to connect to host with supplied info.")


vms = filter(lambda vm: vm.name.startswith(args.stack_name), get_vms(si))

desc = None
if args.description:
    desc = args.description

tasks = map(lambda vm: vm.CreateSnapshot_Task(name=args.name, description=desc, memory=True, quiesce=False), vms)

for task in tasks:
    WaitForTask(task)
