create table if not exists public.app_shared_config (
    id text primary key,
    data jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

alter table public.app_shared_config enable row level security;

create policy "shared config can be read anonymously"
on public.app_shared_config for select
using (true);

create policy "shared config can be inserted anonymously"
on public.app_shared_config for insert
with check (true);

create policy "shared config can be updated anonymously"
on public.app_shared_config for update
using (true)
with check (true);
