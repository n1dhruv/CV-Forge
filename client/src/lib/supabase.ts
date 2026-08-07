import { createClient } from '@supabase/supabase-js'

const url=process.env.NEXT_PUBLIC_SUPABASE_URL!
const publishableKey=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!

if(!url||!publishableKey)throw new Error('Missing Supabase settings. Copy .env.example to .env and add the project URL and publishable key.')

export const supabase=createClient(url,publishableKey)
