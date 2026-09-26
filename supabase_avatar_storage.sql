insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', true)
on conflict (id) do update set public = true;

drop policy if exists "avatars can be read publicly" on storage.objects;
create policy "avatars can be read publicly"
on storage.objects for select
using (bucket_id = 'avatars');

drop policy if exists "avatars can be uploaded anonymously" on storage.objects;
create policy "avatars can be uploaded anonymously"
on storage.objects for insert
with check (bucket_id = 'avatars');

drop policy if exists "avatars can be updated anonymously" on storage.objects;
create policy "avatars can be updated anonymously"
on storage.objects for update
using (bucket_id = 'avatars')
with check (bucket_id = 'avatars');