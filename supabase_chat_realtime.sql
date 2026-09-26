do $$
begin
    alter publication supabase_realtime add table public.chat_messages;
exception
    when duplicate_object then null;
end
$$;