import { NextResponse } from "next/server";
import { auth } from "@/shared/lib/auth";

const PUBLIC_PATHS = new Set(["/login", "/unauthorized"]);

export default auth((req) => {
  const { pathname } = req.nextUrl;

  if (PUBLIC_PATHS.has(pathname)) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  if (!req.auth) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  if (req.auth.error === "RefreshTokenError") {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  // Forward the access token via internal header so downstream
  // handlers and server components don't need to call auth() again.
  const headers = new Headers(req.headers);
  headers.set("x-auth-token", req.auth.accessToken);
  return NextResponse.next({ request: { headers } });
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
