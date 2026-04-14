import Keycloak from "next-auth/providers/keycloak";
import NextAuth from "next-auth";
import type { NextAuthConfig } from "next-auth";

async function refreshAccessToken(token: {
  refreshToken: string;
  [key: string]: unknown;
}) {
  const url = `${process.env.KEYCLOAK_ISSUER}/protocol/openid-connect/token`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      client_id: process.env.KEYCLOAK_CLIENT_ID!,
      client_secret: process.env.KEYCLOAK_CLIENT_SECRET!,
      refresh_token: token.refreshToken,
    }),
  });
  if (!resp.ok) throw new Error("RefreshTokenError");
  const data = await resp.json();
  return {
    ...token,
    accessToken: data.access_token,
    refreshToken: data.refresh_token ?? token.refreshToken,
    expiresAt: Math.floor(Date.now() / 1000) + data.expires_in,
  };
}

export const authConfig: NextAuthConfig = {
  providers: [
    Keycloak({
      clientId: process.env.KEYCLOAK_CLIENT_ID!,
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET!,
      issuer: process.env.KEYCLOAK_ISSUER!,
    }),
  ],
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        token.accessToken = account.access_token as string;
        token.refreshToken = account.refresh_token as string;
        token.expiresAt = account.expires_at as number;
        return token;
      }
      // Return token if not expired
      if (Date.now() < token.expiresAt * 1000 - 60_000) {
        return token;
      }
      // Token expired — attempt refresh
      try {
        return await refreshAccessToken(token);
      } catch {
        return { ...token, error: "RefreshTokenError" as const };
      }
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      session.error = token.error;
      return session;
    },
  },
  cookies: {
    sessionToken: {
      name: "authjs.investor-session-token",
      options: {
        httpOnly: true,
        sameSite: "strict",
        path: "/",
        secure: process.env.NODE_ENV === "production",
      },
    },
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
