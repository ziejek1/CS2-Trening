do $$
begin
    alter publication supabase_realtime add table public.chat_messages;
exception
    when duplicate_object then null;
end
$$;

do $$
declare
    target_table text;
begin
    foreach target_table in array array[
        'user_presence',
        'user_training_data',
        'app_shared_config'
    ]
    loop
        begin
            execute format(
                'alter publication supabase_realtime add table public.%I',
                target_table
            );
        exception
            when duplicate_object then null;
        end;
    end loop;
end
$$;

do $$
declare
    target_table text;
begin
    foreach target_table in array array[
        'user_presence',
        'user_training_data',
        'app_shared_config'
    ]
    loop
        begin
            execute format(
                'alter publication supabase_realtime add table public.%I',
                target_table
            );
        exception
            when duplicate_object then null;
        end;
    end loop;
end
$$;