import gpu


vertex_shader = '''
uniform mat4 ModelViewProjectionMatrix;

in vec3 pos;
uniform vec4 color;

out vec4 finalColor;

void main()
{
  vec4 p = ModelViewProjectionMatrix * vec4(pos, 1.0);
  
  //cheap z offset good enough for now...
  p.w += 0.0001;
  
  gl_Position = p;
  finalColor = color;
}
''' 

fragment_shader = '''
in vec4 finalColor;
out vec4 fragColor;

void main()
{
  fragColor = finalColor;
}
'''


def uniform_color_offset():
    return gpu.types.GPUShader(vertex_shader, fragment_shader)