-- Run in Supabase SQL Editor.
create extension if not exists pgcrypto;

create table if not exists public.reviews (
  id uuid primary key default gen_random_uuid(),
  reviewer_name text not null check (char_length(reviewer_name) between 1 and 80),
  reviewer_email text not null check (char_length(reviewer_email) between 3 and 160),
  category text not null check (char_length(category) between 1 and 80),
  rating smallint not null check (rating between 1 and 5),
  review_text text not null check (char_length(review_text) between 10 and 700),
  consent boolean not null default false check (consent = true),
  status text not null default 'pending' check (status in ('pending','approved','archived')),
  featured boolean not null default false,
  created_at timestamptz not null default now(),
  approved_at timestamptz
);

create table if not exists public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

alter table public.reviews enable row level security;
alter table public.admin_users enable row level security;

create policy "Anyone can submit a pending review" on public.reviews
for insert to anon, authenticated
with check (status='pending' and featured=false and approved_at is null and consent=true);

create policy "Public can read approved reviews" on public.reviews
for select to anon, authenticated
using (status='approved' or exists(select 1 from public.admin_users a where a.user_id=auth.uid()));

create policy "Admins can update reviews" on public.reviews
for update to authenticated
using (exists(select 1 from public.admin_users a where a.user_id=auth.uid()))
with check (exists(select 1 from public.admin_users a where a.user_id=auth.uid()));

create policy "Admins can delete reviews" on public.reviews
for delete to authenticated
using (exists(select 1 from public.admin_users a where a.user_id=auth.uid()));

create policy "Admins can see their admin record" on public.admin_users
for select to authenticated
using (user_id=auth.uid());

create index if not exists reviews_public_order on public.reviews(status, featured desc, approved_at desc);
