/**
 * CloudFlare Worker to handle chunked transfers for Docker Registry
 * This worker buffers chunked requests and forwards them with Content-Length
 */

export default {
async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Only process registry PATCH requests (blob uploads)
    if (!url.pathname.startsWith('/v2/') || request.method !== 'PATCH') {
      // Pass through non-PATCH requests unchanged
      return fetch(request);
    }

    console.log(`Processing ${request.method} ${url.pathname}`);
    
    try {
      // Check if request uses chunked encoding
      const transferEncoding = request.headers.get('transfer-encoding');
      const contentLength = request.headers.get('content-length');
      
      if (transferEncoding?.includes('chunked') || !contentLength) {
        console.log('Buffering chunked request...');
        
        // Buffer the entire request body
        const bodyArrayBuffer = await request.arrayBuffer();
        const bodySize = bodyArrayBuffer.byteLength;
        
        console.log(`Buffered ${bodySize} bytes`);
        
        // Create new headers without chunked encoding
        const newHeaders = new Headers(request.headers);
        newHeaders.delete('transfer-encoding');
        newHeaders.set('content-length', bodySize.toString());
        
        // Forward the request with buffered body
        const newRequest = new Request(request.url, {
          method: request.method,
          headers: newHeaders,
          body: bodyArrayBuffer,
        });
        
        const response = await fetch(newRequest);
        console.log(`Origin responded with ${response.status}`);
        
        return response;
      }
      
      // Non-chunked requests pass through
      return fetch(request);
      
    } catch (error) {
      console.error('Worker error:', error);
      
      // Return error response
      return new Response(
        JSON.stringify({
          error: 'Worker processing failed',
          message: error.message
        }),
        {
          status: 502,
          headers: {
            'content-type': 'application/json',
            'x-worker-error': error.message
          }
        }
      );
    }
  }
};