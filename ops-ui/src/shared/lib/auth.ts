import NextAuth from "next-auth";

declare module "next-auth" {
  interface Session {
    accessToken: string;
    platformRole: string;
    error?: "RefreshTokenError";
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken: string;
    refreshToken: string;
    expiresAt: number;
    platformRole: string;
    error?: "RefreshTokenError";
  }
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

const clientId = requireEnv("AUTH_KEYCLOAK_ID");
const browserIssuer = requireEnv("NEXT_PUBLIC_KEYCLOAK_ISSUER");
const serverIssuer = requireEnv("AUTH_KEYCLOAK_ISSUER");
const serverOidc = `${serverIssuer}/protocol/openid-connect`;
const browserOidc = `${browserIssuer}/protocol/openid-connect`;

async function refreshAccessToken(
  token: import("next-auth/jwt").JWT,
): Promise<import("next-auth/jwt").JWT> {
  const response = await fetch(`${serverOidc}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: clientId,
      grant_type: "refresh_token",
      refresh_token: token.refreshToken,
    }),
  });

  if (!response.ok) {
    return { ...token, error: "RefreshTokenError" };
  }

  const data = await response.json();
  return {
    ...token,
    accessToken: data.access_token,
    refreshToken: data.refresh_token ?? token.refreshToken,
    expiresAt: Math.floor(Date.now() / 1000) + data.expires_in,
  };
}

function extractPlatformRole(accessToken: string): string {
  try {
    const payload = JSON.parse(atob(accessToken.split(".")[1]));
    const roles: string[] = payload.realm_access?.roles ?? [];
    if (roles.includes("ops_admin")) return "ops_admin";
    if (roles.includes("ops_viewer")) return "ops_viewer";
    return "ops_viewer";
  } catch {
    return "ops_viewer";
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    {
      id: "keycloak",
      name: "Keycloak",
      type: "oidc",
      clientId,
      issuer: browserIssuer,
      authorization: {
        url: `${browserOidc}/auth`,
        params: { scope: "openid profile email" },
      },
      token: `${serverOidc}/token`,
      userinfo: `${serverOidc}/userinfo`,
      jwks_endpoint: `${serverOidc}/certs`,
    },
  ],
  cookies: {
    sessionToken: {
      name: "authjs.ops-session-token",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: process.env.NODE_ENV === "production",
      },
    },
  },
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        const at = account.access_token ?? "";
        return {
          ...token,
          accessToken: at,
          refreshToken: account.refresh_token ?? "",
          expiresAt: account.expires_at ?? 0,
          platformRole: extractPlatformRole(at),
        };
      }

      if (Date.now() < token.expiresAt * 1000 - 60_000) {
        return token;
      }

      const refreshed = await refreshAccessToken(token);
      return { ...refreshed, platformRole: extractPlatformRole(refreshed.accessToken) };
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      session.platformRole = token.platformRole;
      session.error = token.error;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
});
