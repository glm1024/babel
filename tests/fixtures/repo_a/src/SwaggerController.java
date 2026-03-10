import io.swagger.annotations.Api;
import io.swagger.annotations.ApiImplicitParam;
import io.swagger.annotations.ApiOperation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.*;

@Api(tags = "用户接口")
@io.swagger.v3.oas.annotations.tags.Tag(name = "标签接口")
public class SwaggerController {
    @ApiOperation
    (
        value = "查询用户列表",
        notes = "分页查询用户"
    )
    @ApiImplicitParam(name = "userId", value = "用户编号")
    @io.swagger.v3.oas.annotations.Operation(summary = "创建用户", description = "创建一个新用户")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(description = "请求成功")
    @io.swagger.v3.oas.annotations.parameters.RequestBody(description = "请求体说明")
    public void create(
        @Parameter(description = "用户名称")
        String name,
        @Schema(description = "年龄字段")
        String age) {
    }
}
