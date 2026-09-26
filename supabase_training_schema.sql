create table if not exists public.user_training_data (
    username text primary key,
    data jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

alter table public.user_training_data enable row level security;

create policy "training data can be read anonymously"
on public.user_training_data for select
using (true);

create policy "training data can be inserted anonymously"
on public.user_training_data for insert
with check (true);

create policy "training data can be updated anonymously"
on public.user_training_data for update
using (true)
with check (true);
