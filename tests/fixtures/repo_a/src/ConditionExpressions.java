public class ConditionExpressions {
    public boolean check(String message, String defaultMessage, String value) {
        if (message.contains("SnowFlakeGenerator:时钟回拨")) {
            return true;
        }
        if ("不能为null".equals(defaultMessage)) {
            return false;
        }
        if (value.startsWith("指定范围")) {
            return true;
        }
        switch (value) {
            case "停止服务":
                return true;
            default:
                break;
        }
        assert "断言命中".equals(defaultMessage);
        return false;
    }

    public boolean normalize(String message, String value) {
        if (message.replace("错误前缀:", "").equals("停止服务")) {
            return true;
        }
        if (message.replaceAll("租户[0-9]+", "租户").contains("租户")) {
            return true;
        }
        if (message.replaceFirst("提示:", "").startsWith("告警")) {
            return true;
        }
        if (message.split("，")[0].contentEquals("忽略")) {
            return true;
        }
        if (value.regionMatches(0, "前缀", 0, 2)) {
            return true;
        }
        return false;
    }

    public void guard(String value) {
        Assert.hasText(value, "名称不能为空");
        Assert.isTrue(value.replace("前缀", "").equals("启用"), "状态非法");
    }

    public String rewrite(String value) {
        return value.replace("启动虚拟机：", "开启云主机：").replace("虚拟机：", "云主机：");
    }

    public boolean isHan(char c) {
        if (c >= '\u4e00' && c <= '\u9fa5') {
            return true;
        }
        return false;
    }

    public void decorate(java.util.List<String> values) {
        values.add("启用");
    }
}
