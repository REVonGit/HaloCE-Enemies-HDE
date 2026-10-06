// meshtool simplify <in> <out> <target_tris> <max_error>   |   meshtool unwrap <in> <out> <resolution>
// binary: uint32 nv, uint32 nt, float pos[nv*3], uint32 idx[nt*3]; unwrap output adds float uv[nv*2] and uint32 xref[nv]
#include "meshoptimizer.h"
#include "xatlas.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <string>
static void rd(const char* p, std::vector<float>& P, std::vector<unsigned>& I) {
  FILE* f = fopen(p, "rb"); unsigned nv, nt; fread(&nv, 4, 1, f); fread(&nt, 4, 1, f);
  P.resize(nv * 3); I.resize(nt * 3); fread(P.data(), 4, nv * 3, f); fread(I.data(), 4, nt * 3, f); fclose(f);
}
int main(int argc, char** argv) {
  std::string cmd = argv[1]; std::vector<float> P; std::vector<unsigned> I; rd(argv[2], P, I);
  size_t nv = P.size() / 3;
  if (cmd == "simplify") {
    size_t target = atoi(argv[4]) * 3; float err = atof(argv[5]);
    std::vector<unsigned> remap(nv);
    size_t uv = meshopt_generateVertexRemap(remap.data(), I.data(), I.size(), P.data(), nv, 12);
    std::vector<float> P2(uv * 3); std::vector<unsigned> I2(I.size());
    meshopt_remapVertexBuffer(P2.data(), P.data(), nv, 12, remap.data());
    meshopt_remapIndexBuffer(I2.data(), I.data(), I.size(), remap.data());
    std::vector<unsigned> out(I2.size()); float le = 0;
    size_t n = meshopt_simplify(out.data(), I2.data(), I2.size(), P2.data(), uv, 12, target, err, 0, &le);
    if (n > target * 1.5) n = meshopt_simplify(out.data(), I2.data(), I2.size(), P2.data(), uv, 12, target, err * 4, 0, &le);
    if (n > target * 1.5) {
      // sloppy (clustering) undershoots on meshes made of many separate pieces: raise its target until it lands
      size_t t2 = target;
      for (int it = 0; it < 8; it++) {
        n = meshopt_simplifySloppy(out.data(), I2.data(), I2.size(), P2.data(), uv, 12, t2, 1.0f, &le);
        if (n >= target * 0.8 || t2 >= I2.size()) break;
        t2 = (size_t)(t2 * (double)target / (n ? n : 3) * 1.05); t2 -= t2 % 3;
      }
    }
    out.resize(n);
    std::vector<unsigned> r2(uv); size_t un = meshopt_optimizeVertexFetchRemap(r2.data(), out.data(), out.size(), uv);
    std::vector<float> P3(un * 3); meshopt_remapVertexBuffer(P3.data(), P2.data(), uv, 12, r2.data()); meshopt_remapIndexBuffer(out.data(), out.data(), out.size(), r2.data());
    FILE* f = fopen(argv[3], "wb"); unsigned a = un, b = out.size() / 3; fwrite(&a, 4, 1, f); fwrite(&b, 4, 1, f);
    fwrite(P3.data(), 4, P3.size(), f); fwrite(out.data(), 4, out.size(), f); fclose(f);
    fprintf(stderr, "simplify %zu -> %u tris, error %g\n", I.size() / 3, b, le);
  } else {
    xatlas::Atlas* at = xatlas::Create();
    xatlas::MeshDecl md; md.vertexCount = nv; md.vertexPositionData = P.data(); md.vertexPositionStride = 12;
    md.indexCount = I.size(); md.indexData = I.data(); md.indexFormat = xatlas::IndexFormat::UInt32;
    xatlas::AddMesh(at, md);
    xatlas::ChartOptions co; co.maxIterations = 4;
    xatlas::PackOptions po; po.resolution = atoi(argv[4]); po.padding = 2; po.bilinear = true; po.blockAlign = false;
    xatlas::Generate(at, co, po);
    const xatlas::Mesh& m = at->meshes[0];
    FILE* f = fopen(argv[3], "wb"); unsigned a = m.vertexCount, b = m.indexCount / 3; fwrite(&a, 4, 1, f); fwrite(&b, 4, 1, f);
    for (unsigned i = 0; i < m.vertexCount; i++) { unsigned x = m.vertexArray[i].xref; fwrite(&P[x * 3], 4, 3, f); }
    fwrite(m.indexArray, 4, m.indexCount, f);
    for (unsigned i = 0; i < m.vertexCount; i++) { float uv[2] = { m.vertexArray[i].uv[0] / at->width, m.vertexArray[i].uv[1] / at->height }; fwrite(uv, 4, 2, f); }
    for (unsigned i = 0; i < m.vertexCount; i++) fwrite(&m.vertexArray[i].xref, 4, 1, f);
    fclose(f); fprintf(stderr, "unwrap: %u verts %u charts atlas %ux%u\n", m.vertexCount, at->chartCount, at->width, at->height);
    xatlas::Destroy(at);
  }
}
