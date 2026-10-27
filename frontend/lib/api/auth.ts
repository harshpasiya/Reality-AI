export type UserRole = "customer" | "broker";

export type User = {
  id: number;
  email: string;
  name: string;
  role: UserRole;
};

export type RegisterRequest = {
  name: string;
  email: string;
  password: string;
  role: UserRole;
};

export type RegisterResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export async function registerUser(
  data: RegisterRequest,
): Promise<RegisterResponse> {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/auth/register`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    },
  );

  if (!response.ok) {
    throw new Error("Registration failed");
  }

  return response.json();
}

export async function loginUser(data: LoginRequest): Promise<LoginResponse> {
  const API_URL = process.env.NEXT_PUBLIC_API_URL;

  if (!API_URL) {
    throw new Error("API URL is not configured.");
  }

  const body = new URLSearchParams();
  body.append("username", data.email);
  body.append("password", data.password);

  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: body.toString(),
  });

  if (!response.ok) {
    let message = "Login failed. Please check your email and password.";

    try {
      const errorData = await response.json();

      if (typeof errorData?.detail === "string") {
        message = errorData.detail;
      }
    } catch {
      // Keep default message
    }

    throw new Error(message);
  }

  return response.json();
}
