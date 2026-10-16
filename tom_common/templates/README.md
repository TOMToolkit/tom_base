# How tom_common/templates is organized
_These are developer docs for the `tom_common/templates` directory explaining why
things are named the way they are and some conventions about updating overridden
templates_.

Django resolves a template name like `account/login.html` by searching each installed app's
`templates/` directory in `INSTALLED_APPS` order. The first match wins, and `tom_common` is listed
before `allauth` in `TOMTOOLKIT_INSTALLED_APPS` for exactly that reason: a file here with the same
path as a file in another package replaces that package's template.

Consequently, most directory names here are not a choice — they are lookup keys owned by the package being overridden and cannot be renamed:

| Directory | Whose name it is | What it holds |
|---|---|---|
| `account/` | django-allauth | Per-page copies of allauth account templates (login, signup closed, inactive account). Each copy's header comment names its divergence from allauth's original — re-check them when upgrading allauth. `account/email/` holds our registration emails, following allauth's `<prefix>_subject.txt` / `<prefix>_message.txt` mail convention. |
| `allauth/` | django-allauth | `layouts/base.html` bridges allauth's page blocks into `tom_common/base.html`; `elements/` restyles allauth's form/button/panel building blocks with Bootstrap 5. |
| `mfa/` | django-allauth | Per-page copies of allauth MFA templates (same conventions as `account/`). |
| `comments/`, `django_comments/` | django-contrib-comments | That package looks templates up under both prefixes; the split is theirs, not ours. |
| `django_filters/` | django-filter | Widget template override. |
| `404.html` | Django | Project-level error page (Django looks for it at the template root). |
| `tom_common/` | tom_common | Our own pages and partials, under the standard app-namespace convention. |
| `auth/` | tom_common (historical name) | Our own user/group management pages — **not** overrides: `django.contrib.auth` ships no templates for these views. The name predates this convention being written down. |
| `bootstrap5_overrides/` | tom_common (historical name) | Consumed by our own `bootstrap5_overrides` template tags — overrides nothing in django-bootstrap5. |

The last two rows are named as if they override a third-party package but are really ours; folding
them into `tom_common/` is a planned cleanup. It is a breaking change for any TOM that overrides
those template paths, so it waits for a release that can carry the notice.


## Conventions to facilitate upgrading an overriden template

_When TOM Toolkit overrides a template from a third party app, and that app is
updated, we must re-integrate our overrides into any changed templates from that
app. These conventions are intended to facilitate that update._

### Marker convention for the per-page allauth copies (`account/`, `mfa/`)

Edited copies mark every divergent line or block:
 - a single changed line gets a trailing
`{# TOM Toolkit ... #}` comment,
- a contiguous block gets a
`{# --- TOM Toolkit addition: begin/end --- #}` pair.

Upgrading `django-allauth` means replacing the unmarked content with
allauth's new template and re-applying the marked lines. When the entire
allauth template has been replaced (i.e. nothing of allauth's retained),
our full replacements have no marking comments, but say so in their header
comment.
