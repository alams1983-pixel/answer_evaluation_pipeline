import { NextRequest, NextResponse } from 'next/server';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ sheetId: string; pageNo: string }> }
) {
  const { sheetId, pageNo } = await params;
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

  // Try cookie first, then query param fallback
  const token = request.cookies.get('auth_token')?.value
    || request.nextUrl.searchParams.get('t')
    || null;

  if (!token) {
    return new NextResponse('No auth token', { status: 401 });
  }

  const headers: HeadersInit = {
    'Authorization': `Bearer ${token}`,
  };

  try {
    const res = await fetch(
      `${API_BASE}/files/sheets/${sheetId}/pages/${pageNo}`,
      { headers }
    );

    if (!res.ok) {
      const errBody = await res.text().catch(() => '');
      console.error(
        `[image-proxy] Backend returned ${res.status} for sheet=${sheetId} page=${pageNo}: ${errBody}`
      );
      if (res.status === 404) {
        return new NextResponse('Not found', { status: 404 });
      }
      return new NextResponse(`Backend error: ${res.status}`, { status: res.status });
    }

    const blob = await res.blob();
    const contentType = res.headers.get('content-type') || 'image/png';

    return new NextResponse(blob, {
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=3600',
      },
    });
  } catch (err) {
    console.error(`[image-proxy] Network error: ${err}`);
    return new NextResponse('Network error', { status: 502 });
  }
}
