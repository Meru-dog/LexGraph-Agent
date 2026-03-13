-- Run in Supabase SQL editor: https://app.supabase.com/project/_/sql

-- DD Agent Tasks
create table if not exists dd_tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  status text not null default 'running',
  prompt text,
  jurisdiction text,
  model_name text default 'gemini',
  transaction_type text,
  current_step int default 0,
  step_label text,
  report jsonb,
  error text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Contract Review Tasks
create table if not exists review_tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  status text not null default 'running',
  document_id text,
  jurisdiction text,
  contract_type text,
  result jsonb,
  error text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- User profiles (extends auth.users)
create table if not exists profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  role text default 'attorney',
  avatar_url text,
  updated_at timestamptz default now()
);

-- Auto-create profile on signup
create or replace function handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, full_name, role)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
    'attorney'
  );
  return new;
end;
$$ language plpgsql security definer;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure handle_new_user();

-- RLS policies
alter table dd_tasks enable row level security;
alter table review_tasks enable row level security;
alter table profiles enable row level security;

create policy "Users can manage own DD tasks"
  on dd_tasks for all using (auth.uid() = user_id);

create policy "Users can manage own review tasks"
  on review_tasks for all using (auth.uid() = user_id);

create policy "Users can view own profile"
  on profiles for select using (auth.uid() = id);

create policy "Users can update own profile"
  on profiles for update using (auth.uid() = id);
