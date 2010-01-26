#
from logilab.common.compat import chain, imap

from logilab.astng import (ASTNGBuildingException, InferenceError,
                           NotFoundError, NoDefault)
from logilab.astng._nodes import NodeNG, StmtMixIn, BlockRangeMixIn, BaseClass
from logilab.astng.infutils import Instance

"""
Module for all nodes (except scoped nodes).
"""

def unpack_infer(stmt, context=None):
    """return an iterator on nodes inferred by the given statement if the inferred
    value is a list or a tuple, recurse on it to get values inferred by its
    content
    """
    if isinstance(stmt, (List, Tuple)):
        # XXX loosing context
        return chain(*imap(unpack_infer, stmt.elts))
    infered = stmt.infer(context).next()
    if infered is stmt:
        return iter( (stmt,) )
    return chain(*imap(unpack_infer, stmt.infer(context)))



def are_exclusive(stmt1, stmt2, exceptions=None):
    """return true if the two given statements are mutually exclusive

    `exceptions` may be a list of exception names. If specified, discard If
    branches and check one of the statement is in an exception handler catching
    one of the given exceptions.

    algorithm :
     1) index stmt1's parents
     2) climb among stmt2's parents until we find a common parent
     3) if the common parent is a If or TryExcept statement, look if nodes are
        in exclusive branches
    """
    # index stmt1's parents
    stmt1_parents = {}
    children = {}
    node = stmt1.parent
    previous = stmt1
    while node:
        stmt1_parents[node] = 1
        children[node] = previous
        previous = node
        node = node.parent
    # climb among stmt2's parents until we find a common parent
    node = stmt2.parent
    previous = stmt2
    while node:
        if stmt1_parents.has_key(node):
            # if the common parent is a If or TryExcept statement, look if
            # nodes are in exclusive branches
            if isinstance(node, If) and exceptions is None:
                if (node.locate_child(previous)[1]
                    is not node.locate_child(children[node])[1]):
                    return True
            elif isinstance(node, TryExcept):
                c2attr, c2node = node.locate_child(previous)
                c1attr, c1node = node.locate_child(children[node])
                if c1node is not c2node:
                    if ((c2attr == 'body' and c1attr == 'handlers' and children[node].catch(exceptions)) or
                        (c2attr == 'handlers' and c1attr == 'body' and previous.catch(exceptions)) or
                        (c2attr == 'handlers' and c1attr == 'orelse') or
                        (c2attr == 'orelse' and c1attr == 'handlers')):
                        return True
                elif c2attr == 'handlers' and c1attr == 'handlers':
                    return previous is not children[node]
            return False
        previous = node
        node = node.parent
    return False



class Arguments(NodeNG):
    """class representing an Arguments node"""
    def __init__(self, args=None, vararg=None, kwarg=None):
        self.args = args
        self.vararg = vararg
        self.kwarg = kwarg

    def _infer_name(self, frame, name):
        if self.parent is frame:
            return name
        return None

    def format_args(self):
        """return arguments formatted as string"""
        result = [_format_args(self.args, self.defaults)]
        if self.vararg:
            result.append('*%s' % self.vararg)
        if self.kwarg:
            result.append('**%s' % self.kwarg)
        return ', '.join(result)

    def default_value(self, argname):
        """return the default value for an argument

        :raise `NoDefault`: if there is no default value defined
        """
        i = _find_arg(argname, self.args)[0]
        if i is not None:
            idx = i - (len(self.args) - len(self.defaults))
            if idx >= 0:
                return self.defaults[idx]
        raise NoDefault()

    def is_argument(self, name):
        """return True if the name is defined in arguments"""
        if name == self.vararg:
            return True
        if name == self.kwarg:
            return True
        return self.find_argname(name, True)[1] is not None

    def find_argname(self, argname, rec=False):
        """return index and Name node with given name"""
        if self.args: # self.args may be None in some cases (builtin function)
            return _find_arg(argname, self.args, rec)
        return None, None


def _find_arg(argname, args, rec=False):
    for i, arg in enumerate(args):
        if isinstance(arg, Tuple):
            if rec:
                found = _find_arg(argname, arg.elts)
                if found[0] is not None:
                    return found
        elif arg.name == argname:
            return i, arg
    return None, None


def _format_args(args, defaults=None):
    values = []
    if args is None:
        return ''
    if defaults is not None:
        default_offset = len(args) - len(defaults)
    for i, arg in enumerate(args):
        if isinstance(arg, Tuple):
            values.append('(%s)' % _format_args(arg.elts))
        else:
            values.append(arg.name)
            if defaults is not None and i >= default_offset:
                values[-1] += '=' + defaults[i-default_offset].as_string()
    return ', '.join(values)


class AssAttr(NodeNG):
    """class representing an AssAttr node"""


class Assert(StmtMixIn, NodeNG):
    """class representing an Assert node"""


class Assign(StmtMixIn, NodeNG):
    """class representing an Assign node"""


class AugAssign(StmtMixIn, NodeNG):
    """class representing an AugAssign node"""


class Backquote(NodeNG):
    """class representing a Backquote node"""


class BinOp(NodeNG):
    """class representing a BinOp node"""


class BoolOp(NodeNG):
    """class representing a BoolOp node"""


class Break(StmtMixIn, NodeNG):
    """class representing a Break node"""


class CallFunc(NodeNG):
    """class representing a CallFunc node"""

    def __init__(self):
        self.starargs = None
        self.kwargs = None

class Compare(NodeNG):
    """class representing a Compare node"""

    def get_children(self):
        """override get_children for tuple fields"""
        yield self.left
        for _, comparator in self.ops:
            yield comparator # we don't want the 'op'

class Comprehension(NodeNG):
    """class representing a Comprehension node"""


class Const(NodeNG, Instance):
    """represent a Str or Num node"""
    def __init__(self, value=None):
        self.value = value

    def getitem(self, index, context=None):
        if isinstance(self.value, basestring):
            return self.value[index]
        raise TypeError()

    def has_dynamic_getattr(self):
        return False

    def itered(self):
        if isinstance(self.value, basestring):
            return self.value
        raise TypeError()

class Continue(StmtMixIn, NodeNG):
    """class representing a Continue node"""


class Decorators(NodeNG):
    """class representing a Decorators node"""
    def __init__(self, nodes=None):
        self.nodes = nodes

    def scope(self):
        # skip the function node to go directly to the upper level scope
        return self.parent.parent.scope()

class DelAttr(NodeNG):
    """class representing a DelAttr node"""


class Delete(StmtMixIn, NodeNG):
    """class representing a Delete node"""


class Dict(NodeNG, Instance):
    """class representing a Dict node"""

    def pytype(self):
        return '__builtin__.dict'

    def get_children(self):
        """get children of a Dict node"""
        # overrides get_children
        for key, value in self.items:
            yield key
            yield value

    def itered(self):
        return self.items[::2]

    def getitem(self, key, context=None):
        for i in xrange(0, len(self.items), 2):
            for inferedkey in self.items[i].infer(context):
                if inferedkey is YES:
                    continue
                if isinstance(inferedkey, Const) and inferedkey.value == key:
                    return self.items[i+1]
        raise IndexError(key)


class Discard(StmtMixIn, NodeNG):
    """class representing a Discard node"""


class Ellipsis(NodeNG):
    """class representing an Ellipsis node"""


class EmptyNode(NodeNG):
    """class representing an EmptyNode node"""


class ExceptHandler(StmtMixIn, NodeNG):
    """class representing an ExceptHandler node"""

    def __init__(self):
        # XXX parent.lineno is wrong, can't catch the right line ...
        return # XXX it doesn't work yet
        if exc_type and exc_type.lineno:
            self.fromlineno =  exc_type.lineno
        else:
            self.fromlineno =  self.body[0].fromlineno - 1
        self.tolineno = self.body[-1].tolineno
        if name:
            self.blockstart_tolineno = name.tolineno
        elif exc_type:
            self.blockstart_tolineno = exc_type.tolineno
        else:
            self.blockstart_tolineno = self.fromlineno

    def _blockstart_toline(self):
        if self.name:
            return self.name.tolineno
        elif self.type:
            return self.type.tolineno
        else:
            return self.lineno

    def set_line_info(self, lastchild):
        self.fromlineno = self.lineno
        self.tolineno = lastchild.tolineno
        self.blockstart_tolineno = self._blockstart_toline()

    def catch(self, exceptions):
        if self.type is None or exceptions is None:
            return True
        for node in self.type.nodes_of_class(Name):
            if node.name in exceptions:
                return True


class Exec(StmtMixIn, NodeNG):
    """class representing an Exec node"""


class ExtSlice(NodeNG):
    """class representing an ExtSlice node"""


class For(BlockRangeMixIn, StmtMixIn, NodeNG):
    """class representing a For node"""

    def _blockstart_toline(self):
        return self.iter.tolineno


class FromImportMixIn(BaseClass):
    """MixIn for From and Import Nodes"""

    def _infer_name(self, frame, name):
        return name

    def do_import_module(node, modname):
        """return the ast for a module whose name is <modname> imported by <node>
        """
        # handle special case where we are on a package node importing a module
        # using the same name as the package, which may end in an infinite loop
        # on relative imports
        # XXX: no more needed ?
        mymodule = node.root()
        level = getattr(node, 'level', None) # Import as no level
        if mymodule.absolute_modname(modname, level) == mymodule.name:
            # FIXME: I don't know what to do here...
            raise InferenceError('module importing itself: %s' % modname)
        try:
            return mymodule.import_module(modname, level=level)
        except (ASTNGBuildingException, SyntaxError):
            raise InferenceError(modname)

    def real_name(self, asname):
        """get name from 'as' name"""
        for index in range(len(self.names)):
            name, _asname = self.names[index]
            if name == '*':
                return asname
            if not _asname:
                name = name.split('.', 1)[0]
                _asname = name
            if asname == _asname:
                return name
        raise NotFoundError(asname)


class From(FromImportMixIn, StmtMixIn, NodeNG):
    """class representing a From node"""

    def __init__(self,  fromname, names):
        self.modname = fromname
        self.names = names

class Getattr(NodeNG):
    """class representing a Getattr node"""


class Global(StmtMixIn, NodeNG):
    """class representing a Global node"""

    def __init__(self, names):
        self.names = names

    def _infer_name(self, frame, name):
        return name


class If(BlockRangeMixIn, StmtMixIn, NodeNG):
    """class representing an If node"""

    def _blockstart_toline(self):
        return self.test.tolineno

    def block_range(self, lineno):
        """handle block line numbers range for if statements"""
        if lineno == self.body[0].fromlineno:
            return lineno, lineno
        if lineno <= self.body[-1].tolineno:
            return lineno, self.body[-1].tolineno
        return self._elsed_block_range(lineno, self.orelse,
                                       self.body[0].fromlineno - 1)


class IfExp(NodeNG):
    """class representing an IfExp node"""


class Import(FromImportMixIn, StmtMixIn, NodeNG):
    """class representing an Import node"""


class Index(NodeNG):
    """class representing an Index node"""


class Keyword(NodeNG):
    """class representing a Keyword node"""


class List(NodeNG, Instance):
    """class representing a List node"""

    def pytype(self):
        return '__builtin__.list'

    def getitem(self, index, context=None):
        return self.elts[index]

    def itered(self):
        return self.elts


class ListComp(NodeNG):
    """class representing a ListComp node"""


class Pass(StmtMixIn, NodeNG):
    """class representing a Pass node"""


class Print(StmtMixIn, NodeNG):
    """class representing a Print node"""


class Raise(StmtMixIn, NodeNG):
    """class representing a Raise node"""


class Return(StmtMixIn, NodeNG):
    """class representing a Return node"""


class Slice(NodeNG):
    """class representing a Slice node"""


class Subscript(NodeNG):
    """class representing a Subscript node"""


class TryExcept(BlockRangeMixIn, StmtMixIn, NodeNG):
    """class representing a TryExcept node"""
    def _infer_name(self, frame, name):
        return name

    def _blockstart_toline(self):
        return self.lineno

    def block_range(self, lineno):
        """handle block line numbers range for try/except statements"""
        last = None
        for exhandler in self.handlers:
            if exhandler.type and lineno == exhandler.type.fromlineno:
                return lineno, lineno
            if exhandler.body[0].fromlineno <= lineno <= exhandler.body[-1].tolineno:
                return lineno, exhandler.body[-1].tolineno
            if last is None:
                last = exhandler.body[0].fromlineno - 1
        return self._elsed_block_range(lineno, self.orelse, last)


class TryFinally(BlockRangeMixIn, StmtMixIn, NodeNG):
    """class representing a TryFinally node"""

    def _blockstart_toline(self):
        return self.lineno

    def block_range(self, lineno):
        """handle block line numbers range for try/finally statements"""
        child = self.body[0]
        # py2.5 try: except: finally:
        if (isinstance(child, TryExcept) and child.fromlineno == self.fromlineno
            and lineno > self.fromlineno and lineno <= child.tolineno):
            return child.block_range(lineno)
        return self._elsed_block_range(lineno, self.finalbody)


class Tuple(NodeNG, Instance):
    """class representing a Tuple node"""

    def pytype(self):
        return '__builtin__.tuple'

    def getitem(self, index, context=None):
        return self.elts[index]

    def itered(self):
        return self.elts


class UnaryOp(NodeNG):
    """class representing an UnaryOp node"""


class While(BlockRangeMixIn, StmtMixIn, NodeNG):
    """class representing a While node"""

    def _blockstart_toline(self):
        return self.test.tolineno

    def block_range(self, lineno):
        """handle block line numbers range for for and while statements"""
        return self. _elsed_block_range(lineno, self.orelse)

class With(BlockRangeMixIn, StmtMixIn, NodeNG):
    """class representing a With node"""

    def _blockstart_toline(self):
        if self.vars:
            return self.vars.tolineno
        else:
            return self.expr.tolineno


class Yield(NodeNG):
    """class representing a Yield node"""

# constants ##############################################################

CONST_CLS = {
    list: List,
    tuple: Tuple,
    dict: Dict,
    }

def const_factory(value):
    """return an astng node for a python value"""
    try:
        # if value is of class list, tuple, dict use specific class, not Const
        cls = CONST_CLS[value.__class__]
        node = cls()
        if isinstance(node, Dict):
            node.items = ()
        else:
            node.elts = ()
    except KeyError:
        # why was value in (None, False, True) not OK?
        assert isinstance(value, (int, long, complex, float, basestring)) or value in (None, False, True)
        node = Const()
        node.value = value
    return node



