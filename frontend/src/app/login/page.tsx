"use client"

export default function LoginPage() {
  return <LoginForm />
}

function LoginForm() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-900 text-xl font-bold text-white dark:bg-zinc-50 dark:text-zinc-900">
            V
          </div>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight">Welcome back</h1>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Sign in to your account to continue
          </p>
        </div>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault()
            const form = e.currentTarget as HTMLFormElement
            const data = new FormData(form)
            try {
              const { api } = await import("@/lib/api")
              const result = await api.auth.login(
                data.get("username") as string,
                data.get("password") as string
              )
              localStorage.setItem("auth_token", result.access_token)
              localStorage.setItem("auth_user", data.get("username") as string)
              window.location.href = "/dashboard"
            } catch {
              const errorEl = form.querySelector('[role="alert"]')
              if (errorEl) errorEl.textContent = "Invalid username or password"
            }
          }}
        >
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
            >
              Username
            </label>
            <input
              id="username"
              name="username"
              type="text"
              required
              autoComplete="username"
              className="mt-1 block w-full rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-sm placeholder-zinc-400 focus:border-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400/20 dark:border-zinc-800 dark:bg-zinc-950 dark:placeholder-zinc-500"
              placeholder="admin"
            />
          </div>
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
            >
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              className="mt-1 block w-full rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-sm placeholder-zinc-400 focus:border-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400/20 dark:border-zinc-800 dark:bg-zinc-950 dark:placeholder-zinc-500"
              placeholder="••••••••"
            />
          </div>
          <p className="text-xs text-red-500" role="alert" />
          <button
            type="submit"
            className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-800 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            Sign in
          </button>
        </form>
      </div>
    </div>
  )
}
