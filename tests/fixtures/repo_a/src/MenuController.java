public class MenuController {
    @Log(title = "部门管理", businessType = BusinessType.UPDATE)
    public void audit() {
    }

    public Object remove() {
        return AjaxResult.warn("菜单已分配,不允许删除");
    }
}
