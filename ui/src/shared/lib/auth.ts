import NextAuth from "next-auth";

declare module "next-auth" {
  interface Session {
    accessToken: string;
    error?: "RefreshTokenError";
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken: string;
    refreshToken: string;
    expiresAt: number;
    error?: "RefreshTokenError";
  }
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

const clientId = requireEnv("AUTH_KEYCLOAK_ID");
// Browser-facing issuer — used for issuer validation (must match `iss` in callback)
const browserIssuer = requireEnv("NEXT_PUBLIC_KEYCLOAK_ISSUER");
// Server-side Keycloak URL for token exchange, JWKS, userinfo (Docker network)
const serverIssuer = requireEnv("AUTH_KEYCLOAK_ISSUER");
const serverOidc = `${serverIssuer}/protocol/openid-connect`;
const browserOidc = `${browserIssuer}/protocol/openid-connect`;

// In-memory refresh lock — prevents concurrent token refreshes from
// multiple auth() calls in the same request lifecycle.
let refreshPromise: Promise<import("next-auth/jwt").JWT> | null = null;

async function doRefresh(token: import("next-auth/jwt").JWT): Promise<import("next-auth/jwt").JWT> {
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

async function refreshAccessToken(
  token: import("next-auth/jwt").JWT,
): Promise<import("next-auth/jwt").JWT> {
  // Deduplicate concurrent refresh calls — only one HTTP request in flight
  if (!refreshPromise) {
    refreshPromise = doRefresh(token).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
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
      name: "authjs.ui-session-token",
      options: { httpOnly: true, sameSite: "lax", path: "/", secure: false },
    },
  },
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        return {
          ...token,
          accessToken: account.access_token ?? "",
          refreshToken: account.refresh_token ?? "",
          expiresAt: account.expires_at ?? 0,
        };
      }

      // Token still valid (with 60s buffer)
      if (Date.now() < token.expiresAt * 1000 - 60_000) {
        return token;
      }

      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      session.error = token.error;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
});
