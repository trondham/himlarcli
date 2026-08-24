# Deleting object storage when we delete a project

Status: **blocked on an infrastructure decision.** The himlarcli side is
written and committed on the `object_fixes` branch, but it cannot reach the
object storage of another project with the current radosgw configuration.

## The problem

Object storage was never touched when we deleted a project or a user. Instances,
volumes, images, security groups and DNS zones are all purged by
`Keystone.delete_project()`, but containers and objects were left behind in ceph
radosgw forever. There was no object storage client in himlarcli at all.

## What has been implemented

Branch `object_fixes`:

| Commit | Description |
| --- | --- |
| `23457d2` | `feat(object): delete object storage when a project is deleted` |
| `77659d2` | `fix(object): do not fail silently when the account is not in the url` |

- **`himlarcli/swift.py`** (new). Region aware client for swift compatible
  object storage. Lists and deletes containers and objects for a project,
  pages through large listings, deletes `*+segments` containers last, reuses
  one connection per project, retries once with a new token on 401, and
  honours `--dry-run`. Falls back to a plain object delete if radosgw rejects
  `?multipart-manifest=delete`.
- **`himlarcli/keystone.py`**. `delete_project()` now purges all containers for
  the project, per region. This covers `project.py delete`, `user.py delete`,
  `user_cleanup()` and `bin/enddate-delete.sh`, since they all go through this
  one method.
- **`object.py`**. New actions `show` (usage per region), `list` (containers)
  and `purge` (delete everything, `--force` to skip the confirmation).
- **`himlarcli/printer.py`, `project.py`, `report.py`**. Containers are included
  in the project resource reports, so users are told that their object storage
  will be deleted before we delete the project.
- **`config.ini.example`**. New optional `[openstack] object_account_prefix`.

Note that containers belong to a **project** (the object storage account), not
to a user. "The buckets of a user" are the containers in that user's
`PRIVATE-*` and `DEMO-*` projects, which `user_cleanup()` already deletes as
projects. This holds as long as radosgw accounts are per project — see the open
question below.

## Why it does not work on NREC today

The implementation addresses another project's account by rewriting the account
part of the object-store url, the way swift reseller admins do
(`.../swift/v1/AUTH_<project id>`). NREC's radosgw does not accept that.

Tested against project `iaas-team` (`e3dcca3452924794a6aebdd21b5da249`):

```
$ ./object.py show iaas-team --debug
=> use object-store endpoint https://object.api.osl.nrec.no:8080/swift/v1 in osl
=> no object storage account for project e3dcca3452924794a6aebdd21b5da249 in osl
```

The endpoint in the service catalog has **no account part**. Two curl requests
with the himlarcli token confirm what that means:

```
$ curl -s -o /dev/null -D- -H "X-Auth-Token: $TOKEN" \
    https://object.api.osl.nrec.no:8080/swift/v1
HTTP/1.1 204 No Content
X-Account-Container-Count: 0
X-Account-Object-Count: 0
X-Account-Bytes-Used: 0

$ curl -s -o /dev/null -D- -H "X-Auth-Token: $TOKEN" \
    https://object.api.osl.nrec.no:8080/swift/v1/AUTH_e3dcca3452924794a6aebdd21b5da249
HTTP/1.1 404 Not Found
```

The bare endpoint returns account headers, i.e. **the account is decided by the
token alone** (`rgw swift account in url = false`). The `AUTH_<project id>` form
is therefore parsed as a *container name* inside the himlarcli user's own
account, which does not exist, hence 404. No amount of url rewriting can reach
another project's storage in this configuration.

Commit `77659d2` makes this loud instead of silent. Before it, a project delete
called the purge, got a 404, read it as "this project never used object
storage" and deleted nothing without a word. Now it prints:

```
Swift: the object-store endpoint https://object.api.osl.nrec.no:8080/swift/v1
in osl has no account in the url (rgw swift account in url = false). Object
storage for other projects can not be reached, and will NOT be deleted!
```

**Current state: nothing is deleted, and nothing is silently wrong.** Project
deletion is otherwise unaffected.

## Open question that decides the approach

Are containers owned per **project** or per **user**? With
`rgw keystone implicit tenants` a keystone user can be mapped to a radosgw user
inside a tenant named after the project (`<project id>$<user id>`), which would
mean each user in a project has a separate container namespace. That changes
both the implementation and what "delete the object storage of a project" means.

Run on `osl-rgw-01`:

```bash
radosgw-admin bucket list | grep -i e3dcca3452924794a6aebdd21b5da249
radosgw-admin user list | head
radosgw-admin --show-config | grep -E 'swift_account_in_url|implicit_tenants'
```

- Buckets listed as `e3dcca…/<name>` (tenant = project) → accounts are per
  project, option 2 below is viable.
- Buckets owned per user (`e3dcca…$<user id>`) → accounts are per user,
  option 2 is out and option 3 is the only complete answer.

## Options

### Option 1: address the account in the url (infrastructure change)

Make radosgw accept the account in the url, then the code already on the branch
works unchanged.

Infrastructure changes:

1. **radosgw** (himlar puppet): set `rgw swift account in url = true`.
2. **keystone catalog**, both regions: re-register the object-store endpoint
   with the account template, e.g.
   `https://object.api.osl.nrec.no:8080/swift/v1/AUTH_%(project_id)s`
   (keystone substitutes the project id per token).
3. **radosgw**: make sure a role the himlarcli user holds is listed in
   `rgw keystone accepted admin roles`. himlarcli authenticates as an admin
   user, so if `admin` is already in that list, no new role assignment is
   needed. Otherwise add a `ResellerAdmin` role and grant it to the himlarcli
   user.
4. **himlarcli**: nothing, once the endpoint carries the account part. As an
   interim step, before the endpoint is re-registered, set
   `object_account_prefix=AUTH_` in `/etc/himlarcli/config.ini` — the code then
   builds the account url itself.

Impact and risk:

- Every user's catalog entry for object storage changes. Clients that read the
  catalog (openstack CLI, swift CLI, horizon, most SDKs) follow automatically;
  anyone with a hardcoded storage url has to update it.
- The S3 API is unaffected. Existing containers are unaffected — the setting
  controls url parsing, not account naming.
- Needs verification in a test environment first (`test02` / `dev`), since it
  touches how every object storage client reaches the service.

Verdict: least code, but it changes a user facing endpoint and needs a
coordinated puppet + keystone change.

### Option 2: project scoped tokens (himlarcli change only)

Get a keystone token scoped to the target project and use the bare endpoint,
which then resolves to that project's account.

Changes:

- **Infrastructure**: none.
- **himlarcli**: `Swift` builds its own session with `project_id` set to the
  target project instead of reusing the shared session. The himlarcli user
  needs a role assignment in the target project to get such a token, so the
  flow becomes grant role → purge → revoke role, using the existing
  `grant_role()` / `revoke_role()`.

Caveats:

- **Only works if radosgw accounts are per project.** If they are per user, the
  himlarcli user's account in that project is empty and we would purge nothing
  while reporting success — the exact failure mode we just fixed.
- Mutating role assignments as a side effect of a delete is noisy in the audit
  log, and a crash mid-run leaks a role assignment. Acceptable here since the
  project is deleted immediately afterwards, but it is not clean.

Verdict: no infrastructure change, but only correct in the per-project case,
and it needs the open question answered first.

### Option 3: radosgw admin ops API (recommended)

Skip the swift API and use radosgw's admin ops API, which is designed for
exactly this and is independent of keystone scoping.

Infrastructure changes:

1. **radosgw**: create a dedicated admin user and note its keys:
   ```bash
   radosgw-admin user create --uid=himlarcli \
       --display-name="himlarcli object storage admin" \
       --caps="buckets=*;users=read;metadata=read"
   ```
2. **radosgw**: confirm the admin API is enabled and reachable —
   `rgw enable apis` must include `admin` (default), entry point
   `rgw admin entry` (default `admin`).
3. **firewall / access**: the admin endpoint must be reachable from the hosts
   that run himlarcli (`osl-proxy-01`, `bgo-proxy-01`).
4. **himlarcli config**: new section per region with the endpoint, access key
   and secret key. These are powerful credentials (full bucket and user
   control) and must be treated like the openstack admin password.

himlarcli changes:

- New dependency for SigV4 signing (`requests-aws4auth`, or boto3).
- New client, `himlarcli/rgw.py`, replacing `swift.py` for the delete path:
  - list buckets for a project: `GET /admin/bucket?format=json&stats=true`,
    filtered on the project's tenant, or `?uid=<tenant>$<user id>`
  - delete a bucket and its contents in one call:
    `DELETE /admin/bucket?bucket=<name>&tenant=<tenant>&purge-objects=true`
- `object.py` and the report functions keep their current shape, only the
  client behind them changes.

Advantages:

- Works whether accounts are per project or per user.
- Catches buckets created through the **S3** API as well, which the swift path
  may not.
- `purge-objects=true` deletes server side, instead of one HTTP request per
  object. Materially faster for large accounts.
- No dependency on catalog layout, keystone roles or url parsing.

Verdict: most robust and the only option that answers the per-user case. Costs
one more credential to manage and a new dependency.

## Recommendation

1. Answer the open question with `radosgw-admin bucket list` on `osl-rgw-01`.
2. Implement **option 3**. It is the only approach that is correct regardless of
   how radosgw maps keystone users to accounts, and it also covers S3 buckets.
3. Keep `swift.py` for the read only paths (`object.py show` / `list`) if the
   admin API turns out to be inconvenient for usage reporting, otherwise drop
   it when `rgw.py` lands.

If option 3 is rejected on the grounds of a second credential set, option 1 is
the fallback, on the condition that the endpoint change is tested in `dev` or
`test02` first.

Until one of them is implemented, deleted projects keep leaving their object
storage behind, and the error message from `77659d2` is the only thing telling
us so.
