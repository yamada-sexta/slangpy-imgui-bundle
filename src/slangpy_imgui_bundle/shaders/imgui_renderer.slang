struct Uniforms
{
    float4x4 proj;
    Texture2D<float4> texture;
    SamplerState sampler;
};

ConstantBuffer<Uniforms> uniforms;

struct VertexInput
{
    float2 pos : POSITION;
    float2 uv : TEXCOORD0;
    float4 col : COLOR0;
};

struct PixelInput
{
    float4 pos : SV_POSITION;
    float2 uv;
    float4 col;
};

[shader("vertex")]
PixelInput vertexMain(VertexInput vIn)
{
    PixelInput vOut;
    vOut.pos = mul(uniforms.proj, float4(vIn.pos.xy, 0.0, 1.0));
    vOut.col = vIn.col;
    vOut.uv = vIn.uv;
    return vOut;
}

[shader("fragment")]
float4 fragmentMain(PixelInput pIn)
    : SV_Target
{
    return pIn.col * uniforms.texture.Sample(uniforms.sampler, pIn.uv);
}
