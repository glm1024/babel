public class ConsoleLogger {
    public void print() {
        logger.info("日志输出中文");
        System.out.println("控制台输出中文");
        System.err.println("错误流输出中文");
    }
}
