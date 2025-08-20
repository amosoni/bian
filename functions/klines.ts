export const onRequestGet = async ({ request }: { request: Request }) => {
	const url = new URL(request.url)
	const qs = url.search
	const upstreams = [
		'https://fapi1.binance.com',
		'https://fapi2.binance.com',
		'https://fapi3.binance.com',
		'https://fapi4.binance.com',
		'https://testnet.binancefuture.com',
	]

	for (const base of upstreams) {
		try {
			const r = await fetch(`${base}/fapi/v1/klines${qs}`, {
				// small cache on edge; harmless for live view
				// @ts-ignore cloudflare specific
				cf: { cacheTtl: 3, cacheEverything: false },
				headers: { 'accept': 'application/json' },
			})
			if (r.ok) {
				const body = await r.text()
				return new Response(body, {
					headers: {
						'content-type': 'application/json; charset=utf-8',
						'access-control-allow-origin': '*',
						'access-control-allow-methods': 'GET, OPTIONS',
					},
				})
			}
		} catch (e) {
			continue
		}
	}
	return new Response(JSON.stringify({ error: 'upstream failed' }), {
		status: 502,
		headers: {
			'content-type': 'application/json; charset=utf-8',
			'access-control-allow-origin': '*',
		},
	})
}

export const onRequestOptions = async () => {
	return new Response(null, {
		status: 204,
		headers: {
			'access-control-allow-origin': '*',
			'access-control-allow-methods': 'GET, OPTIONS',
			'access-control-allow-headers': '*',
		},
	})
} 