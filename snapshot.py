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
import argparse
import requests

from pyVim.connect import SmartConnect, SmartConnectNoSSL, Disconnect
from pyVmomi import vim
from pyVim.task import WaitForTask

from tools import cli

import pptree

requests.packages.urllib3.disable_warnings()

class Actions:
    CREATE = 0
    SWITCH = 1
    REMOVE = 2
    TREE = 3

def setup_args():
    parser = cli.build_arg_parser()
    parser.add_argument('--stack-name', required=True,
                        help="stack name")
    parser.add_argument('--create', required=False,
                        dest="action", action="store_const", const=Actions.CREATE,
                        help="Create snapshot")
    parser.add_argument('--switch', required=False,
                        dest="action", action="store_const", const=Actions.SWITCH,
                        help="Switch to snapshot")
    parser.add_argument('--remove', required=False,
                        dest="action", action="store_const", const=Actions.REMOVE,
                        help="Remove snapshot")
    parser.add_argument('--tree', required=False,
                        dest="action", action="store_const", const=Actions.TREE,
                        help="Show snapshot tree")
    parser.add_argument('--description', required=False,
                        help="Description for the snapshot")
    parser.add_argument('--name', required=False,
                        help="Name for the Snapshot")
    args = parser.parse_args()
    if args.action is None:
        parser.print_help()
        exit(1)

    return cli.prompt_for_password(args)

def get_vms(si):
    content = si.RetrieveContent()

    container = content.rootFolder  # starting point to look into
    viewType = [vim.VirtualMachine]  # object types to look for
    recursive = True  # whether we should look into it recursively
    containerView = content.viewManager.CreateContainerView(container, viewType, recursive)

    children = containerView.view
    for child in children:
        yield child

def create_snapshot(si, stack_name, name, description):
    vms = filter(lambda vm: vm.name.startswith(stack_name), get_vms(si))
    desc = None
    if description:
        desc = description

    tasks = map(lambda vm: vm.CreateSnapshot_Task(name=name, description=desc, memory=True, quiesce=False), vms)

    for task in tasks:
        WaitForTask(task)

def list_snapshots(si, stack_name):
    vms = filter(lambda vm: vm.name.startswith(stack_name), get_vms(si))
    for vm in vms:
        currentSnapshotTree = _get_vm_snapshot_recursively(vm.snapshot.rootSnapshotList, lambda snapshotTree: snapshotTree.snapshot == vm.snapshot.currentSnapshot)
        print ("'%s' current snapshot '%s'" % (vm.name, currentSnapshotTree.name))
        for rootSnapshot in vm.snapshot.rootSnapshotList:
            pptree.print_tree(rootSnapshot, "childSnapshotList", "name", last="down")

def _get_vm_snapshot_recursively(snapshots, matcher):
    for snapshot in snapshots:
        if matcher(snapshot):
            return snapshot
        else:
            childSnapshot = _get_vm_snapshot_recursively(snapshot.childSnapshotList, matcher)
            if childSnapshot:
                return childSnapshot

    return None

def switch_to_snapshot(si, stack_name, snapshot_name):
    vms = filter(lambda vm: vm.name.startswith(stack_name), get_vms(si))
    tasks = []
    for vm in vms:
        snapshotTree = _get_vm_snapshot_recursively(vm.snapshot.rootSnapshotList, lambda snapshotTree: snapshotTree.name == snapshot_name)
        if snapshotTree:
            print ("Switching %s to %s" % (vm.name, snapshot_name))
            tasks.append(snapshotTree.snapshot.RevertToSnapshot_Task())
        else:
            print ("%s have no snapshot %s" % (vm.name, snapshot_name))

    for task in tasks:
        WaitForTask(task)


if __name__ == "__main__":
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

    if args.action == Actions.CREATE:
        create_snapshot(si, args.stack_name, args.name, args.description)
    elif args.action == Actions.TREE:
        list_snapshots(si, args.stack_name)
    elif args.action == Actions.SWITCH:
        switch_to_snapshot(si, args.stack_name, args.name)
    else:
        exit(1)
