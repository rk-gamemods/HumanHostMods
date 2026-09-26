"""Adapters for the pinned TypeTreeGenerator/UnityPy boundary."""
from UnityPy.helpers import TypeTreeHelper
from UnityPy.helpers.TypeTreeNode import TypeTreeNode


def normalize_generated(node):
    # Generator 0.0.10 labels arrays of strings/primitives with their element
    # type. UnityPy checks primitive types before Array children, so a string[]
    # would otherwise be read as one string. Ordinary string/char arrays stay strings.
    children = node.m_Children
    node_type = node.m_Type
    if children and children[0].m_Type == "Array" and len(children[0].m_Children) == 2:
        element = children[0].m_Children[1]
        if node.m_Type in TypeTreeHelper.FUNCTION_READ_MAP and not (node.m_Type == "string" and element.m_Type == "char"):
            node_type = "vector"
    # Reconstruct rather than mutate: UnityPyBoost caches the type discriminator
    # at construction, independently of the public m_Type property.
    normalized_children = [normalize_generated(child) for child in children]
    if [c.m_Name for c in children[:4]] == ["m_GameObject", "m_Enabled", "m_Script", "m_Name"]:
        enabled = normalized_children[1]
        normalized_children[1] = TypeTreeNode(enabled.m_Level, enabled.m_Type, enabled.m_Name,
                                             enabled.m_ByteSize, enabled.m_Version,
                                             m_Children=enabled.m_Children,
                                             m_MetaFlag=(enabled.m_MetaFlag or 0) | 0x4000)
    return TypeTreeNode(node.m_Level, node_type, node.m_Name, node.m_ByteSize, node.m_Version,
                        m_Children=normalized_children,
                        m_MetaFlag=node.m_MetaFlag, m_TypeFlags=node.m_TypeFlags,
                        m_Index=node.m_Index, m_RefTypeHash=node.m_RefTypeHash)


def read_with_managed_references(obj, node, generator):
    """Fallback for stripped SerializeReference schemas, confined to this process.

    Catalog decoding is single-threaded. Restore the library hooks even on error.
    The Python reader exposes the serialized class/namespace/assembly triple that
    is needed to reconstruct a missing reference-type layout.
    """
    original = TypeTreeHelper.get_ref_type_node
    boost = TypeTreeHelper.read_typetree_boost

    def resolve(ref_object, assets):
        try:
            result = original(ref_object, assets)
            if result is not None:
                return result
        except ValueError:
            pass
        typ = ref_object["type"]
        if not typ["class"]:
            return None
        cls = ((typ["ns"] + ".") if typ["ns"] else "") + typ["class"]
        generated = normalize_generated(generator.get_nodes_up(typ["asm"], cls))
        # The generator always prepends a Unity object header. SerializeReference
        # values are inline managed classes and do not contain that header.
        if [c.m_Name for c in generated.m_Children[:4]] != ["m_GameObject", "m_Enabled", "m_Script", "m_Name"]:
            raise ValueError("Unexpected generated managed-reference header")
        return TypeTreeNode(generated.m_Level, generated.m_Type, generated.m_Name,
                            generated.m_ByteSize, generated.m_Version,
                            m_Children=generated.m_Children[4:], m_MetaFlag=generated.m_MetaFlag)

    try:
        TypeTreeHelper.get_ref_type_node = resolve
        TypeTreeHelper.read_typetree_boost = None
        return obj.read_typetree(nodes=node)
    finally:
        TypeTreeHelper.get_ref_type_node = original
        TypeTreeHelper.read_typetree_boost = boost
