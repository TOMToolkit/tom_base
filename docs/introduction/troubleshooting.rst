Troubleshooting your TOM
========================

When first installing or later updating your TOM, you may run into a few
common issues. Fortunately, you can stand on our shoulders and hopefully
find a solution here!

Check that you’ve migrated
--------------------------

Oftentimes, updating the TOM Toolkit requires running migrations.
Usually, a directive to do so will be included in the release notes, or
Django will remind you that ``You have unapplied migrations``. If you
don’t happen to see those, you may also see a
``<tablename.column> does not exist`` when you load a page, or an error
about an ``applabel``. Those are generally indicators that you need to
run a database migration.

You can confirm that you are missing a migration by running:

::

   ./manage.py showmigrations --list

Migrations that have been applied will have a ``[X]`` next to them, so
make sure they all have one. If any are missing:

::

   ./manage.py migrate

Make sure you’re in a virtual environment
-----------------------------------------

Everyone forgets to activate their virtualenv from time to time. If you
get a missing package or some such, ensure that you’ve activated your
virtualenv:

::

   source env/bin/activate

You may need to adapt the above for your particular shell. Also be sure
that the virtualenv was created with a compatible version of Python, and
that you installed your dependencies into that virtualenv.

Check your shell
----------------

It’s a small development team, and we all use bash. We’ve seen some
issues with people running zsh, fish, and even csh. You may need to
adapt the commands given in the setup guide.
