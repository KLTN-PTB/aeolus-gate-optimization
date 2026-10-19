export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((e: {loc?: string[]; msg?: string}) => `${e.loc?.slice(1).join('.')}: ${e.msg}`).join(' · ')
      : 'Không thể kết nối backend. Vui lòng thử lại.');
  }
  return data;
}
