create table if not exists public.app_users (
    username text primary key,
    data jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

alter table public.app_users enable row level security;

drop policy if exists "users can be read anonymously" on public.app_users;
create policy "users can be read anonymously"
on public.app_users for select
using (true);

drop policy if exists "users can be inserted anonymously" on public.app_users;
create policy "users can be inserted anonymously"
on public.app_users for insert
with check (true);

drop policy if exists "users can be updated anonymously" on public.app_users;
create policy "users can be updated anonymously"
on public.app_users for update
using (true)
with check (true);

drop policy if exists "users can be deleted anonymously" on public.app_users;
create policy "users can be deleted anonymously"
on public.app_users for delete
using (true);