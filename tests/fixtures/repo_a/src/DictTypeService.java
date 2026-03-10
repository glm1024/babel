public class DictTypeService {
    public void delete(String name) {
        throw new ServiceException(String.format("%1$s已分配,不能删除", name));
    }
}
