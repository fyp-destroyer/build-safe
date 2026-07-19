"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "motion/react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { DotMatrixReveal } from "./DotMatrixReveal";
import { IconCheck, IconSend } from "@/lib/icons";
import { apiFetch, ApiError } from "@/lib/api";
import { setToken, setStoredUser } from "@/lib/auth";
import type { TokenResponse } from "@/lib/types";

type Step = "form" | "success";
type Mode = "login" | "register";

const COPY: Record<
  Mode,
  { emailTitle: string; emailSubtitle: string; successTitle: string; successSubtitle: string; cta: string }
> = {
  login: {
    emailTitle: "Welcome back",
    emailSubtitle: "Sign in to continue",
    successTitle: "You're in!",
    successSubtitle: "Welcome back to BuildSafe AI",
    cta: "Continue to Chat",
  },
  register: {
    emailTitle: "Create your account",
    emailSubtitle: "Get started with BuildSafe AI",
    successTitle: "Account created",
    successSubtitle: "Welcome to BuildSafe AI",
    cta: "Continue to Chat",
  },
};

// react-hook-form + zod per repo convention for auth forms. Real email +
// password JWT auth (backend: POST /auth/register | /auth/login — see
// schemas/auth.py). Register requires name + email + password (min 8,
// matching the backend's Field(min_length=8)); login requires only email +
// password. No fake 6-digit code step — the backend has no equivalent.
function buildSchema(mode: Mode) {
  return z
    .object({
      name: z.string(),
      email: z.string().trim().min(1, "Email is required").email("Enter a valid email address"),
      password: z.string().min(1, "Password is required"),
    })
    .superRefine((data, ctx) => {
      if (mode === "register") {
        if (!data.name.trim()) {
          ctx.addIssue({ code: "custom", path: ["name"], message: "Full name is required" });
        }
        if (data.password.length < 8) {
          ctx.addIssue({
            code: "custom",
            path: ["password"],
            message: "Password must be at least 8 characters",
          });
        }
      }
    });
}

type FormValues = { name: string; email: string; password: string };

export function EmailCodeAuth({ mode }: { mode: Mode }) {
  const copy = COPY[mode];
  const router = useRouter();

  const [step, setStep] = useState<Step>("form");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(() => buildSchema(mode), [mode]);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", email: "", password: "" },
  });

  const onSubmit = async (data: FormValues) => {
    setFormError(null);
    setSubmitting(true);
    try {
      const path = mode === "register" ? "/auth/register" : "/auth/login";
      const body =
        mode === "register"
          ? { email: data.email, password: data.password, name: data.name }
          : { email: data.email, password: data.password };

      const result = await apiFetch<TokenResponse>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });

      setToken(result.access_token);
      setStoredUser(result.user);
      setStep("success");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 422 && err.fields?.length) {
          const detail = err.fields
            .map((f) => f.msg)
            .filter((msg): msg is string => Boolean(msg))
            .join(" ");
          setFormError(detail || err.message);
        } else {
          setFormError(err.message);
        }
      } else {
        setFormError("Couldn't reach the server. Check your connection and try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen w-full flex-col items-center justify-center overflow-hidden text-white">
      <div className="absolute inset-0">
        <DotMatrixReveal reverse={step === "success"} animationSpeed={step === "success" ? 4 : 3} />
      </div>

      <div className="absolute left-6 top-6 z-10 flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#F97316] text-sm font-bold text-white">
          B
        </div>
        <span className="text-sm font-semibold text-white/90">BuildSafe AI</span>
      </div>

      <div className="relative z-10 w-full max-w-sm px-4">
        {step === "form" ? (
          <motion.div
            key="form-step"
            initial={{ opacity: 0, x: -60 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="space-y-6 text-center"
          >
            <div className="space-y-1">
              <h1 className="text-3xl font-bold tracking-tight">{copy.emailTitle}</h1>
              <p className="text-lg font-light text-white/60">{copy.emailSubtitle}</p>
            </div>

            <div className="space-y-4">
              <button
                type="button"
                className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-3 text-sm text-white backdrop-blur-sm transition-colors hover:bg-white/10"
              >
                <span className="text-base font-semibold">G</span>
                {mode === "login" ? "Sign in with Google" : "Sign up with Google"}
              </button>

              <div className="flex items-center gap-4">
                <div className="h-px flex-1 bg-white/10" />
                <span className="text-sm text-white/40">or</span>
                <div className="h-px flex-1 bg-white/10" />
              </div>

              <form onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate>
                {mode === "register" && (
                  <div className="space-y-1">
                    <input
                      type="text"
                      placeholder="Full name"
                      {...register("name")}
                      className="w-full rounded-full border border-white/10 bg-transparent px-4 py-3 text-center text-white outline-none backdrop-blur-sm placeholder:text-white/40 focus:border-white/30"
                    />
                    {errors.name && (
                      <p className="text-xs text-red-400">{errors.name.message}</p>
                    )}
                  </div>
                )}

                <div className="space-y-1">
                  <input
                    type="email"
                    placeholder="you@example.com"
                    {...register("email")}
                    className="w-full rounded-full border border-white/10 bg-transparent px-4 py-3 text-center text-white outline-none backdrop-blur-sm placeholder:text-white/40 focus:border-white/30"
                  />
                  {errors.email && (
                    <p className="text-xs text-red-400">{errors.email.message}</p>
                  )}
                </div>

                <div className="space-y-1">
                  <div className="relative">
                    <input
                      type="password"
                      placeholder="Password"
                      autoComplete={mode === "register" ? "new-password" : "current-password"}
                      {...register("password")}
                      className="w-full rounded-full border border-white/10 bg-transparent px-4 py-3 text-center text-white outline-none backdrop-blur-sm placeholder:text-white/40 focus:border-white/30"
                    />
                    <button
                      type="submit"
                      disabled={submitting}
                      aria-label="Continue"
                      className="absolute right-1.5 top-1.5 flex h-9 w-9 cursor-pointer items-center justify-center rounded-full bg-[#F97316] text-white transition-colors hover:bg-[#EA580C] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <IconSend width={15} height={15} />
                    </button>
                  </div>
                  {errors.password && (
                    <p className="text-xs text-red-400">{errors.password.message}</p>
                  )}
                </div>

                {formError && (
                  <div
                    role="alert"
                    className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-300"
                  >
                    {formError}
                  </div>
                )}
              </form>
            </div>

            <p className="pt-6 text-xs text-white/40">
              By continuing, you agree to BuildSafe AI&apos;s Terms and Privacy Notice.
            </p>

            <p className="text-sm text-white/50">
              {mode === "login" ? (
                <>
                  Don&apos;t have an account?{" "}
                  <Link href="/register" className="font-semibold text-[#F97316] hover:text-[#FB923C]">
                    Sign up
                  </Link>
                </>
              ) : (
                <>
                  Already have an account?{" "}
                  <Link href="/login" className="font-semibold text-[#F97316] hover:text-[#FB923C]">
                    Log in
                  </Link>
                </>
              )}
            </p>
          </motion.div>
        ) : (
          <motion.div
            key="success-step"
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: "easeOut", delay: 0.2 }}
            className="space-y-6 text-center"
          >
            <div className="space-y-1">
              <h1 className="text-3xl font-bold tracking-tight">{copy.successTitle}</h1>
              <p className="text-lg font-light text-white/50">{copy.successSubtitle}</p>
            </div>

            <motion.div
              initial={{ scale: 0.7, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.35 }}
              className="py-6"
            >
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#F97316]">
                <IconCheck width={26} height={26} className="text-white" />
              </div>
            </motion.div>

            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.7 }}
              onClick={() => router.push("/chat")}
              className="w-full cursor-pointer rounded-full bg-[#F97316] py-3 font-medium text-white transition-colors hover:bg-[#EA580C]"
            >
              {copy.cta}
            </motion.button>
          </motion.div>
        )}
      </div>
    </div>
  );
}
