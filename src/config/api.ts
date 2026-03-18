export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'https://goorm-trip-back.onrender.com';

// 공통 헤더들
export const COMMON_HEADERS = {
  'Content-Type': 'application/json',
  'X-User-Id': '1',
};
