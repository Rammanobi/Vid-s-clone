"use client"

import { useState } from "react"
import { BadgeCheck, Lock, Link as LinkIcon, User } from "lucide-react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { formatNumber } from "@/lib/utils"
import type { Account } from "@/lib/api"

interface ProfileCardProps {
  account: Account
  className?: string
}

export function ProfileCard({ account, className }: ProfileCardProps) {
  const [imgError, setImgError] = useState(false)

  const showAvatar = account.profilePicUrl && !imgError

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-start gap-4 space-y-0">
        <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
          {showAvatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={account.profilePicUrl}
              alt={`${account.username}'s avatar`}
              className="h-full w-full object-cover"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <User className="h-7 w-7 text-zinc-400" aria-hidden="true" />
            </div>
          )}
        </div>

        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <h3 className="truncate text-base font-semibold leading-tight">
              {account.fullName || account.username}
            </h3>
            {account.isVerified && (
              <BadgeCheck
                className="h-4 w-4 shrink-0 fill-blue-500 text-white"
                aria-label="Verified account"
              />
            )}
            {account.isPrivate && (
              <Lock className="h-3.5 w-3.5 shrink-0 text-zinc-400" aria-label="Private account" />
            )}
          </div>
          <p className="truncate text-sm text-zinc-500 dark:text-zinc-400">
            @{account.username}
          </p>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {account.biography && (
          <p className="whitespace-pre-line text-sm text-zinc-700 dark:text-zinc-300">
            {account.biography}
          </p>
        )}

        <div className="flex items-center gap-6 text-sm">
          <div>
            <span className="font-semibold">{formatNumber(account.followerCount ?? 0)}</span>{" "}
            <span className="text-zinc-500 dark:text-zinc-400">followers</span>
          </div>
          <div>
            <span className="font-semibold">{formatNumber(account.followingCount ?? 0)}</span>{" "}
            <span className="text-zinc-500 dark:text-zinc-400">following</span>
          </div>
          <div>
            <span className="font-semibold">{formatNumber(account.postsCount ?? 0)}</span>{" "}
            <span className="text-zinc-500 dark:text-zinc-400">posts</span>
          </div>
        </div>

        {account.externalUrl && (
          <a
            href={account.externalUrl}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            <LinkIcon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span className="truncate">{account.externalUrl}</span>
          </a>
        )}
      </CardContent>
    </Card>
  )
}
