"use client"

import { PageHeader } from '@/components/PageHeader'
import { ProfileEditor } from '@/components/ProfileEditor'

export default function ProfilePage() {
  return (
    <div className="container-normal py-10 md:py-12">
      <PageHeader eyebrow="Resume identity" title="Profile" description="These details appear in your tailored resume header. Only saved values are used." />
      <div className="max-w-3xl rounded-xl border bg-surface p-6 shadow-sm sm:p-8">
        <ProfileEditor />
      </div>
    </div>
  )
}
