"use client";

import { useState, FormEvent, ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { registerUser } from "@/lib/api/auth";
import type { RegisterRequest } from "@/lib/api/auth";
import { useAuthStore } from "@/stores/authStore";

interface FormErrors {
  name?: string;
  email?: string;
  password?: string;
  role?: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);

  const [formData, setFormData] = useState<RegisterRequest>({
    name: "",
    email: "",
    password: "",
    role: "customer",
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<{
    name?: boolean;
    email?: boolean;
    password?: boolean;
    role?: boolean;
  }>({});
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const validateName = (name: string): string | undefined => {
    if (!name.trim()) {
      return "Name is required";
    }
    if (name.trim().length < 2) {
      return "Name must be at least 2 characters";
    }
    return undefined;
  };

  const validateEmail = (email: string): string | undefined => {
    if (!email.trim()) {
      return "Email is required";
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      return "Please enter a valid email address";
    }
    return undefined;
  };

  const validatePassword = (password: string): string | undefined => {
    if (!password) {
      return "Password is required";
    }
    if (password.length < 6) {
      return "Password must be at least 6 characters";
    }
    return undefined;
  };

  const validateRole = (role: string): string | undefined => {
    if (!role || (role !== "customer" && role !== "broker")) {
      return "Please select a role";
    }
    return undefined;
  };

  const validateForm = () => {
    const nameError = validateName(formData.name);
    const emailError = validateEmail(formData.email);
    const passwordError = validatePassword(formData.password);
    const roleError = validateRole(formData.role);

    const newErrors: FormErrors = {};
    if (nameError) newErrors.name = nameError;
    if (emailError) newErrors.email = emailError;
    if (passwordError) newErrors.password = passwordError;
    if (roleError) newErrors.role = roleError;

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Real-time validation if touched
    if (touched[name as keyof FormErrors]) {
      if (name === "name") {
        setErrors((prev) => ({ ...prev, name: validateName(value) }));
      } else if (name === "email") {
        setErrors((prev) => ({ ...prev, email: validateEmail(value) }));
      } else if (name === "password") {
        setErrors((prev) => ({ ...prev, password: validatePassword(value) }));
      } else if (name === "role") {
        setErrors((prev) => ({ ...prev, role: validateRole(value) }));
      }
    }
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setTouched((prev) => ({ ...prev, [name]: true }));

    if (name === "name") {
      setErrors((prev) => ({ ...prev, name: validateName(value) }));
    } else if (name === "email") {
      setErrors((prev) => ({ ...prev, email: validateEmail(value) }));
    } else if (name === "password") {
      setErrors((prev) => ({ ...prev, password: validatePassword(value) }));
    } else if (name === "role") {
      setErrors((prev) => ({ ...prev, role: validateRole(value) }));
    }
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setTouched({ name: true, email: true, password: true, role: true });

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);
    setErrors({});

    try {
      const response = await registerUser(formData);

      setAuth(response.access_token, response.user);

      if (response.user.role === "broker") {
        router.push("/broker/dashboard");
      } else {
        router.push("/");
      }
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Registration failed. Please try again.";

      setErrors({
        email: message,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-zinc-50 via-white to-zinc-100 px-4 py-12 dark:from-zinc-950 dark:via-zinc-900 dark:to-zinc-950">
      <div className="w-full max-w-md">
        {/* Brand / Header Icon */}
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-500/20">
            <svg
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"
              />
            </svg>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-white">
            Create Account
          </h1>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Join us to explore properties and manage listings.
          </p>
        </div>

        {/* Card Container */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl shadow-zinc-200/50 backdrop-blur-sm sm:p-8 dark:border-zinc-800 dark:bg-zinc-900/90 dark:shadow-none">
          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            {/* Name Field */}
            <div className="space-y-1.5">
              <label
                htmlFor="name"
                className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                Full Name
              </label>
              <div className="relative">
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="John Doe"
                  autoComplete="name"
                  className={`w-full rounded-xl border bg-zinc-50/50 px-3.5 py-2.5 text-sm text-zinc-900 transition-colors outline-none placeholder:text-zinc-400 dark:bg-zinc-800/50 dark:text-zinc-100 dark:placeholder:text-zinc-500 ${
                    errors.name
                      ? "border-red-500 focus:border-red-500 focus:ring-4 focus:ring-red-500/10 dark:border-red-500"
                      : "border-zinc-300 hover:border-zinc-400 focus:border-blue-600 focus:ring-4 focus:ring-blue-600/10 dark:border-zinc-700 dark:hover:border-zinc-600"
                  }`}
                  aria-invalid={Boolean(errors.name)}
                  aria-describedby={errors.name ? "name-error" : undefined}
                />
              </div>
              {errors.name && (
                <p
                  id="name-error"
                  className="mt-1 flex items-center gap-1 text-xs text-red-600 dark:text-red-400"
                >
                  <svg
                    className="h-3.5 w-3.5 shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                  {errors.name}
                </p>
              )}
            </div>

            {/* Email Field */}
            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                Email address
              </label>
              <div className="relative">
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="name@example.com"
                  autoComplete="email"
                  className={`w-full rounded-xl border bg-zinc-50/50 px-3.5 py-2.5 text-sm text-zinc-900 transition-colors outline-none placeholder:text-zinc-400 dark:bg-zinc-800/50 dark:text-zinc-100 dark:placeholder:text-zinc-500 ${
                    errors.email
                      ? "border-red-500 focus:border-red-500 focus:ring-4 focus:ring-red-500/10 dark:border-red-500"
                      : "border-zinc-300 hover:border-zinc-400 focus:border-blue-600 focus:ring-4 focus:ring-blue-600/10 dark:border-zinc-700 dark:hover:border-zinc-600"
                  }`}
                  aria-invalid={Boolean(errors.email)}
                  aria-describedby={errors.email ? "email-error" : undefined}
                />
              </div>
              {errors.email && (
                <p
                  id="email-error"
                  className="mt-1 flex items-center gap-1 text-xs text-red-600 dark:text-red-400"
                >
                  <svg
                    className="h-3.5 w-3.5 shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                  {errors.email}
                </p>
              )}
            </div>

            {/* Password Field */}
            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="Create a password"
                  autoComplete="new-password"
                  className={`w-full rounded-xl border bg-zinc-50/50 px-3.5 py-2.5 pr-10 text-sm text-zinc-900 transition-colors outline-none placeholder:text-zinc-400 dark:bg-zinc-800/50 dark:text-zinc-100 dark:placeholder:text-zinc-500 ${
                    errors.password
                      ? "border-red-500 focus:border-red-500 focus:ring-4 focus:ring-red-500/10 dark:border-red-500"
                      : "border-zinc-300 hover:border-zinc-400 focus:border-blue-600 focus:ring-4 focus:ring-blue-600/10 dark:border-zinc-700 dark:hover:border-zinc-600"
                  }`}
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={
                    errors.password ? "password-error" : undefined
                  }
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute top-1/2 right-3 -translate-y-1/2 p-1 text-zinc-400 transition-colors hover:text-zinc-600 dark:hover:text-zinc-200"
                >
                  {showPassword ? (
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"
                      />
                    </svg>
                  ) : (
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                      />
                    </svg>
                  )}
                </button>
              </div>
              {errors.password && (
                <p
                  id="password-error"
                  className="mt-1 flex items-center gap-1 text-xs text-red-600 dark:text-red-400"
                >
                  <svg
                    className="h-3.5 w-3.5 shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                  {errors.password}
                </p>
              )}
            </div>

            {/* Role Selection (Radio Buttons) */}
            <fieldset className="space-y-2">
              <legend className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Account Type
              </legend>
              <div className="grid grid-cols-2 gap-3">
                <label
                  htmlFor="role-customer"
                  className={`relative flex cursor-pointer items-center rounded-xl border p-3.5 transition-all ${
                    formData.role === "customer"
                      ? "border-blue-600 bg-blue-50/50 text-blue-900 ring-2 ring-blue-600/20 dark:bg-blue-950/20 dark:text-blue-100"
                      : "border-zinc-200 bg-zinc-50/30 text-zinc-700 hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-800/30 dark:text-zinc-300 dark:hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="radio"
                      id="role-customer"
                      name="role"
                      value="customer"
                      checked={formData.role === "customer"}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      className="h-4 w-4 cursor-pointer border-zinc-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-600"
                    />
                    <span className="text-sm font-medium">Customer</span>
                  </div>
                </label>

                <label
                  htmlFor="role-broker"
                  className={`relative flex cursor-pointer items-center rounded-xl border p-3.5 transition-all ${
                    formData.role === "broker"
                      ? "border-blue-600 bg-blue-50/50 text-blue-900 ring-2 ring-blue-600/20 dark:bg-blue-950/20 dark:text-blue-100"
                      : "border-zinc-200 bg-zinc-50/30 text-zinc-700 hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-800/30 dark:text-zinc-300 dark:hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="radio"
                      id="role-broker"
                      name="role"
                      value="broker"
                      checked={formData.role === "broker"}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      className="h-4 w-4 cursor-pointer border-zinc-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-600"
                    />
                    <span className="text-sm font-medium">Broker</span>
                  </div>
                </label>
              </div>
              {errors.role && (
                <p
                  id="role-error"
                  className="mt-1 flex items-center gap-1 text-xs text-red-600 dark:text-red-400"
                >
                  <svg
                    className="h-3.5 w-3.5 shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                  {errors.role}
                </p>
              )}
            </fieldset>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="flex w-full cursor-pointer items-center justify-center rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-md shadow-blue-500/20 transition-all hover:bg-blue-700 focus:ring-4 focus:ring-blue-600/20 focus:outline-none active:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading ? (
                <span className="inline-flex items-center gap-2">
                  <svg
                    className="mr-2 -ml-1 h-4 w-4 animate-spin text-white"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Creating account...
                </span>
              ) : (
                "Register"
              )}
            </button>
          </form>

          {/* Login Link */}
          <div className="mt-6 border-t border-zinc-100 pt-5 text-center dark:border-zinc-800">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Already have an account?{" "}
              <Link
                href="/login"
                className="ml-1 font-semibold text-blue-600 transition-colors hover:text-blue-700 hover:underline dark:text-blue-400 dark:hover:text-blue-300"
              >
                Login
              </Link>
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
