# Troubleshooting your TOM Toolkit

When first installing or later updating your TOM, you may run into a few common issues. Fortunately, you can stand on our 
shoulders and hopefully find a solution here!


## Check that you've migrated

Oftentimes, updating the TOM Toolkit requires running migrations. Usually, a directive to do so will be included in the 
release notes, or Django will remind you that `You have unapplied migrations`. If you don't happen to see those, you may 
also see a `<tablename.column> does not exist` when you load a page, or an error about an `applabel`. Those are generally 
indicators that you need to run a database migration.

You can confirm that you are missing a migration by running:

```
./manage.py showmigrations --list
```

Migrations that have been applied will have a `[X]` next to them, so make sure they all have one. If any are missing:

```
./manage.py migrate
```
