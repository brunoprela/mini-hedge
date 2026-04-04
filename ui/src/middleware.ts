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

  // Forward the access token to API proxy routes via internal header
  // so the proxy doesn't need to call auth() again.
  if (pathname.startsWith("/api/proxy") && req.auth.accessToken) {
    const headers = new Headers(req.headers);
    headers.set("x-auth-token", req.auth.accessToken);
    return NextResponse.next({ request: { headers } });
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
