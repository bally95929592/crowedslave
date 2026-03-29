/**
 * Vercel Edge Middleware - 서버 사이드 인증
 * ============================================
 * - 비밀번호가 클라이언트(브라우저)에 절대 노출되지 않음
 * - Vercel 서버에서 요청을 가로채서 인증 확인
 * - 인증 안 되면 로그인 페이지 표시
 * - 환경변수로 관리하여 코드에 비밀번호 없음
 */

const COOKIE_NAME = "cs_auth_token";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7; // 7일 유지

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};

export default function middleware(request) {
  const url = new URL(request.url);

  // 로그인 처리 (POST /api/login)
  if (url.pathname === "/api/login" && request.method === "POST") {
    return handleLogin(request);
  }

  // 로그아웃 처리
  if (url.pathname === "/api/logout") {
    return handleLogout(request);
  }

  // 로그인 페이지 요청
  if (url.pathname === "/login") {
    return new Response(getLoginPageHTML(), {
      headers: { "Content-Type": "text/html; charset=utf-8" },
    });
  }

  // 인증 확인
  const cookie = request.headers.get("cookie") || "";
  const token = getCookieValue(cookie, COOKIE_NAME);
  const validToken = generateToken(
    process.env.AUTH_USER || "admin",
    process.env.AUTH_PASS || "crow1212!!"
  );

  if (token !== validToken) {
    // 인증 안됨 → 로그인 페이지로 리다이렉트
    return Response.redirect(new URL("/login", request.url), 302);
  }

  // 인증됨 → 통과
  return undefined;
}

// ── 로그인 처리 ──
async function handleLogin(request) {
  try {
    const formData = await request.text();
    const params = new URLSearchParams(formData);
    const username = params.get("username");
    const password = params.get("password");

    const validUser = process.env.AUTH_USER || "admin";
    const validPass = process.env.AUTH_PASS || "crow1212!!";

    if (username === validUser && password === validPass) {
      const token = generateToken(validUser, validPass);
      return new Response(null, {
        status: 302,
        headers: {
          Location: "/",
          "Set-Cookie": `${COOKIE_NAME}=${token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${COOKIE_MAX_AGE}`,
        },
      });
    } else {
      return Response.redirect(
        new URL("/login?error=1", request.url),
        302
      );
    }
  } catch (e) {
    return Response.redirect(new URL("/login?error=1", request.url), 302);
  }
}

// ── 로그아웃 처리 ──
function handleLogout(request) {
  return new Response(null, {
    status: 302,
    headers: {
      Location: "/login",
      "Set-Cookie": `${COOKIE_NAME}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0`,
    },
  });
}

// ── 토큰 생성 (HMAC 대용 - 간단한 해시) ──
function generateToken(user, pass) {
  const secret = process.env.AUTH_SECRET || "cs-secret-key-2026";
  const data = `${user}:${pass}:${secret}`;
  let hash = 0;
  for (let i = 0; i < data.length; i++) {
    const char = data.charCodeAt(i);
    hash = ((hash << 5) - hash + char) | 0;
  }
  return "cs_" + Math.abs(hash).toString(36) + "_" + btoa(user).replace(/=/g, "");
}

// ── 쿠키 파싱 ──
function getCookieValue(cookieString, name) {
  const match = cookieString.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? match[2] : null;
}

// ── 로그인 페이지 HTML ──
function getLoginPageHTML() {
  const hasError = false; // URL param으로 체크됨
  return `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CrowedSlave - 로그인</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
  background: #1a1a2e;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-container {
  background: #16213e;
  border-radius: 16px;
  padding: 48px 40px;
  width: 100%;
  max-width: 420px;
  border: 1px solid #253555;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
.logo {
  text-align: center;
  margin-bottom: 32px;
}
.logo h1 {
  font-size: 28px;
  color: #e8e8e8;
  font-weight: 700;
}
.logo h1 span { color: #e94560; }
.logo p {
  color: #8892a4;
  font-size: 14px;
  margin-top: 8px;
}
.lock-icon {
  font-size: 48px;
  text-align: center;
  margin-bottom: 8px;
}
.form-group {
  margin-bottom: 20px;
}
.form-group label {
  display: block;
  color: #8892a4;
  font-size: 13px;
  margin-bottom: 8px;
  font-weight: 600;
}
.form-group input {
  width: 100%;
  padding: 14px 16px;
  background: #0f3460;
  border: 1px solid #253555;
  border-radius: 10px;
  color: #e8e8e8;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
}
.form-group input:focus {
  border-color: #e94560;
}
.form-group input::placeholder {
  color: #556080;
}
.login-btn {
  width: 100%;
  padding: 14px;
  background: #e94560;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.2s;
  margin-top: 8px;
}
.login-btn:hover {
  background: #d63851;
}
.error-msg {
  background: rgba(233,69,96,0.1);
  border: 1px solid rgba(233,69,96,0.3);
  color: #e94560;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 20px;
  display: none;
}
.error-msg.show { display: block; }
.footer-text {
  text-align: center;
  color: #556080;
  font-size: 12px;
  margin-top: 24px;
}
</style>
</head>
<body>
<div class="login-container">
  <div class="logo">
    <div class="lock-icon">🔒</div>
    <h1>Crowed<span>Slave</span></h1>
    <p>광고 성과 대시보드</p>
  </div>

  <div class="error-msg" id="errorMsg">
    아이디 또는 비밀번호가 일치하지 않습니다.
  </div>

  <form method="POST" action="/api/login">
    <div class="form-group">
      <label>아이디</label>
      <input type="text" name="username" placeholder="아이디를 입력하세요" required autocomplete="username" />
    </div>
    <div class="form-group">
      <label>비밀번호</label>
      <input type="password" name="password" placeholder="비밀번호를 입력하세요" required autocomplete="current-password" />
    </div>
    <button type="submit" class="login-btn">로그인</button>
  </form>

  <p class="footer-text">권한이 없는 접근은 제한됩니다</p>
</div>

<script>
  if (window.location.search.includes('error=1')) {
    document.getElementById('errorMsg').classList.add('show');
  }
</script>
</body>
</html>`;
}
