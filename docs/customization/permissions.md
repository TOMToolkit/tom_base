The Permissions System
---

The TOM Toolkit provides a permissions system which can be used to limit the
targets a user or group of users can access. This may be helpful if you have many
users in your TOM but would like to keep some targets proprietary.

Permissions are enforced through groups. Groups can be created and managed by any
PI in the TOM, via the users page. To add a group, simply use the "Add Group"
button found at the top of the groups table:


![](/_static/permissions_doc/addgroup.png)

Modifying a group will allow you to change it's name and add/remove users.

When a user adds or modifies a target, they are able to choose the groups to
assign to the target:


![](/_static/permissions_doc/targetgroups.png)


By default the target will be assigned to all groups the user belongs to.

There is a special group, "Public". By default, all users belong to the Public
group, so all targets assigned to it would be accessible by anyone. The PI does
have the ability to remove users for the Public group, however.


The permissions system is built on top of
[django-guardian](https://django-guardian.readthedocs.io/en/stable/). It has been
kept as simple as possible, but TOM developers may extend the capabilities if
needed.

