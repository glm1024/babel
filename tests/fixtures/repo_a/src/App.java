public class App {
    public String greet() {
        return "欢迎使用";
    }

    public void fail() {
        throw new IllegalArgumentException("参数不能为空");
    }
}

