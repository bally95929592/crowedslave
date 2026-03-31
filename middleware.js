/**
 * Vercel Edge Middleware - Basic Auth 인증
 * - 서버사이드에서 모든 요청을 가로채서 인증 확인
 * - 비밀번호가 브라우저 소스코드에 절대 노출되지 않음
 * - 환경변수로 관리
 */

export const config = {
  matcher: ["/((?!favicon.ico).*)"],
};

export default function middleware(request) {
  const AUTH_USER = process.env.AUTH_USER || "admin";
  const AUTH_PASS = process.env.AUTH_PASS || "crow1212!!";

  const auth = request.headers.get("authorization");

  if (auth) {
    try {
      const base64 = auth.split(" ")[1];
      const decoded = atob(base64);
      const [user, pass] = decoded.split(":");

      if (user === AUTH_USER && pass === AUTH_PASS) {
        return; // 인증 성공 → 정적 파일 서빙
      }
    } catch (e) {
      // 파싱 실패 → 아래에서 401 반환
    }
  }

  // 인증 실패 → 로그인 프롬프트 표시
  return new Response("🔒 CrowedSlave 대시보드\n\n아이디와 비밀번호를 입력하세요.", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="CrowedSlave Dashboard", charset="UTF-8"',
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}
