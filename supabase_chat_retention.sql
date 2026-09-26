create or replace function public.trim_chat_messages()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    delete from public.chat_messages
    where id not in (
        select id
        from public.chat_messages
        order by created_at desc, id desc
        limit 10
    );
    return new;
end;
$$;

drop trigger if exists trim_chat_messages_after_insert on public.chat_messages;

create trigger trim_chat_messages_after_insert
after insert on public.chat_messages
for each statement
execute function public.trim_chat_messages();
