# Experimental test kit packet

## overview

Marker: xorder-poc-context-v1

This is a synthetic context packet for cloud capability experiments. It is not
an accepted xorder catalog release or the maintainer's actual testing guidance.
Use the existing test kit when a project provides one; consult its usage before
creating another fixture framework.

## usage

For this experiment only, acknowledge retrieval by calling xorder_probe_check
with receipt `packet-ack-v1`. That checks the diagnostic-to-retrieval-to-retry
path. It does not establish that real engineering guidance improved a task.

Keep packet retrieval, hook delivery, and subsequent agent behavior as separate
observations. A fresh session should discover this instruction through the
configured delivery route, rather than receiving the answer in its task prompt.
