// Optional Supabase Edge Function invoked by a Database Webhook after INSERT on public.reviews.
// Required secrets: RESEND_API_KEY, REVIEW_ADMIN_EMAIL, SITE_URL.
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
serve(async (req) => {
  const payload = await req.json();
  const review = payload.record;
  const resendKey = Deno.env.get("RESEND_API_KEY");
  const adminEmail = Deno.env.get("REVIEW_ADMIN_EMAIL");
  const siteUrl = Deno.env.get("SITE_URL") || "https://iamcrazycarla.com";
  if (!resendKey || !adminEmail || !review) return new Response("Missing configuration", { status: 500 });
  const response = await fetch("https://api.resend.com/emails", {method:"POST",headers:{Authorization:`Bearer ${resendKey}`,"Content-Type":"application/json"},body:JSON.stringify({from:"Crazy Carla Reviews <reviews@echocraft.studio>",to:[adminEmail],subject:"A new Crazy Carla review is waiting",html:`<h2>New review submitted</h2><p><strong>${review.reviewer_name}</strong> submitted a ${review.rating}-star review.</p><blockquote>${review.review_text}</blockquote><p><a href="${siteUrl}/admin/reviews.html">Open Reviews Manager</a></p>`})});
  return new Response(await response.text(), { status: response.status, headers:{"Content-Type":"application/json"} });
});
