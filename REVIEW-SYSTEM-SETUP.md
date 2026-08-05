# Crazy Carla Review System Setup

The public review cards, separate review form, and private Reviews Manager are built. The system remains in safe preview mode until a Supabase project is connected.

## 1. Create or choose a Supabase project

Open the Supabase SQL Editor and run `supabase/reviews-schema.sql`.

## 2. Connect the website

In Supabase, copy the **Project URL** and **anon public key** from Project Settings > API. Paste them into `js/supabase-config.js`.

Never put the `service_role` key into GitHub or website JavaScript.

## 3. Create Carla's admin login

1. Open Supabase Authentication > Users and invite Carla's email, or have her request a magic link at `/admin/reviews.html` once.
2. Copy her user UUID.
3. In SQL Editor run:

```sql
insert into public.admin_users (user_id)
values ('PASTE-CARLA-AUTH-USER-UUID-HERE')
on conflict do nothing;
```

4. In Authentication > URL Configuration, set the Site URL to `https://iamcrazycarla.com` and add `https://iamcrazycarla.com/admin/reviews.html` as an allowed redirect URL.

## 4. Test the complete workflow

1. Submit a review from the public page.
2. Confirm it does not appear publicly.
3. Sign into `/admin/reviews.html` using Carla's approved email.
4. Approve it and refresh the public page.
5. Unpublish, edit, archive, and delete a test review.

## 5. Optional email notification

The dashboard works without notification email. To email Carla whenever a review arrives:

1. Deploy `supabase/functions/notify-review` as an Edge Function.
2. Add secrets `RESEND_API_KEY`, `REVIEW_ADMIN_EMAIL`, and `SITE_URL`.
3. In Supabase Database > Webhooks, create an INSERT webhook for `public.reviews` pointing to the function.
4. Verify a sending domain in Resend. Until the domain is verified, use a Resend-approved sender address.

The email only tells Carla that a review is waiting and links her to the secure manager. Approval still happens inside the back office.
