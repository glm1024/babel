public class TaskDescriptionProcesses {
    @AsynTask(opType = "JOB_ICOMPUTE_DISABLE_HOST", description = "停用主机")
    public void disableHost() {
    }

    @AsynTaskStep(opType = "JOB_ICOMPUTE_CREATE_NODE", description="创建节点")
    public void createNode() {
    }

    @AsynTask(
        opType = "JOB_ICOMPUTE_DISABLE_HOST",
        description =
            "多行停用主机"
    )
    public void disableHostMultiLine() {
    }

    @AsynTask(opType = "JOB_ICOMPUTE_DISABLE_HOST")
    public void noDescription() {
        String message = "普通字符串";
    }

    @OtherAnnotation(description = "普通描述")
    public void otherAnnotation() {
    }
}
