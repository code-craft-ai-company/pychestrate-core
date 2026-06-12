"""
.. module:: orm
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Contains the ORM associated with the akit database storage

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []
__version__ = "1.0.0"


import enum
import json
import uuid


from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    VARCHAR,
    ForeignKey,
    TEXT,
    UniqueConstraint,
)
from sqlalchemy import inspect, func, text
from sqlalchemy.types import JSON

from sqlalchemy.orm import declarative_base, relationship, backref

from sqlalchemy_utils.types.uuid import UUIDType

from ccai.pychestrate.core.storage.defaults import utc_now

class SerializableModel:
    """
        Mixin style class that adds serialization to data model objects.
    """

    def to_dict(self):
        """
            Iterates the formal data attributes of a model and outputs a dictionary
            with the data based on the model.
        """
        dval = {}

        model = type(self)
        mapper = inspect(model)
        for col in mapper.attrs:
            col_key = col.key
            dval[col_key] = str(getattr(self, col_key))

        return dval


    def to_json(self, indent=4):
        """
            Iterates the formal data attributes of a model and creates a dictionary
            with the data based on the model, then converts the dictionary to a
            JSON string.
        """
        model_dict = self.to_dict()
        json_str = json.dumps(model_dict, indent=indent)
        return json_str


PychestrateModelBase = declarative_base()


class AccountStatus(str, enum.Enum):
    """
        Enum-like class to represent the status of a user or enterprise account.
    """
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    SUSPENDED = 'suspended'
    DELETED = 'deleted'

    @classmethod
    def is_valid(cls, status):
        return status in (cls.ACTIVE, cls.INACTIVE, cls.SUSPENDED, cls.DELETED)


class AuthenticationType(str, enum.Enum):
    """
        Enum-like class to represent the type of authentications that should be used to authenticate the user.
    """
    INTERNAL = 'internal'
    OAUTH = 'oauth2'


class RepositoryType(enum.Enum):
    """Enumeration describing the primary content maintained by a repository."""

    CODE = "code"
    DOCUMENTATION = "documentation"


class RepositoryScope(enum.Enum):
    """Enumeration describing the scope of artifacts provided by a repository."""

    PRODUCT = "product"
    LOCAL = "local"


class WorkQueueJobType(enum.Enum):
    """
        An enumeration that indicates the JobType of a WorkQueue item.  This indicates if a
        work item is a global work item available for execution on any qualified work site or
        if it is a local work item which is meant to execute locally.
    """
    Local = 1
    Global = 2


class WorkQueueState(enum.Enum):
    """
        An enumeration that indicates the JobType of a WorkQueue item.  This indicates if a
        work item is a global work item available for execution on any qualified work site or
        if it is a local work item which is meant to execute locally.
    """
    Enabled = 1
    Disabled = 2


class WorkPacketStatus(enum.Enum):
    """Enumeration of lifecycle states for a :class:`WorkPacket`."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    BLOCKED = "BLOCKED"


class BuildJobTemplate(PychestrateModelBase, SerializableModel):
    """
        A data model that stores global build job templates.
    """

    __tablename__ = "buildjob_template"

    id = Column('bjtmp_id', BigInteger, primary_key=True, autoincrement=True)
    name = Column('bjtmp_name', VARCHAR(128), nullable=False, unique=True)
    description = Column('bjtmp_description', Text, nullable=True)
    specification = Column('bjtmp_specification', JSON, nullable=False)


class BuildTemplate(PychestrateModelBase, SerializableModel):
    """
        A data model that stores global build templates.
    """

    __tablename__ = "build_template"

    id = Column('btmp_id', BigInteger, primary_key=True, autoincrement=True)
    name = Column('btmp_name', VARCHAR(128), nullable=False, unique=True)
    description = Column('btmp_description', Text, nullable=True)
    specification = Column('btmp_specification', JSON, nullable=False)


class TestJobTemplate(PychestrateModelBase, SerializableModel):
    """
        A data model that stores global test job templates.
    """

    __tablename__ = "testjob_template"

    id = Column('tjtmp_id', BigInteger, primary_key=True, autoincrement=True)
    name = Column('tjtmp_name', VARCHAR(128), nullable=False, unique=True)
    description = Column('tjtmp_description', Text, nullable=True)
    specification = Column('tjtmp_specification', JSON, nullable=False)



class Product(PychestrateModelBase, SerializableModel):
    """A data model that represents a product composed from multiple components."""

    __tablename__ = "product"

    id = Column("prod_id", BigInteger, primary_key=True, autoincrement=True)
    name = Column("prod_name", VARCHAR(128), nullable=False, unique=True)
    description = Column("prod_description", Text, nullable=True)

    components = relationship(
        "ProductComponent",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    product_repositories = relationship(
        "ProductToRepository",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    releases = relationship(
        "Release",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProductComponent(PychestrateModelBase, SerializableModel):
    """Represents a component of a product that maps to a source repository."""

    __tablename__ = "product_component"

    __table_args__ = (
        UniqueConstraint("prod_id", "comp_name", name="uq_component_product_name"),
    )

    id = Column("comp_id", BigInteger, primary_key=True, autoincrement=True)
    name = Column("comp_name", VARCHAR(128), nullable=False)
    description = Column("comp_description", Text, nullable=True)

    product_id = Column(
        "prod_id", BigInteger, ForeignKey("product.prod_id"), nullable=False, index=True
    )
    repository_id = Column(
        "repo_id", BigInteger, ForeignKey("repository.repo_id"), nullable=False, index=True
    )

    product = relationship("Product", back_populates="components", lazy="selectin")
    repository = relationship("Repository", back_populates="components", lazy="selectin")


class ProductToRepository(PychestrateModelBase, SerializableModel):
    """Associates product level repositories such as documentation with a product."""

    __tablename__ = "product_to_repository"

    __table_args__ = (
        UniqueConstraint("prod_id", "repo_id", name="uq_product_repository"),
    )

    id = Column("ptor_id", BigInteger, primary_key=True, autoincrement=True)
    product_id = Column(
        "prod_id", BigInteger, ForeignKey("product.prod_id"), nullable=False, index=True
    )
    repository_id = Column(
        "repo_id", BigInteger, ForeignKey("repository.repo_id"), nullable=False, index=True
    )

    product = relationship("Product", back_populates="product_repositories", lazy="selectin")
    repository = relationship("Repository", back_populates="product_links", lazy="selectin")


class ReleaseTrain(PychestrateModelBase, SerializableModel):
    """Represents the symbolic branch structure used to orchestrate a release train."""

    __tablename__ = "release_train"

    id = Column("rtrain_id", BigInteger, primary_key=True, autoincrement=True)
    name = Column("rtrain_name", VARCHAR(128), nullable=False, unique=True)
    description = Column("rtrain_description", Text, nullable=True)

    branches = relationship(
        "ReleaseTrainBranch",
        back_populates="train",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    releases = relationship(
        "Release",
        back_populates="release_train",
        lazy="selectin",
    )


class ReleaseTrainBranchType(str, enum.Enum):
    """Enumerates the logical role a symbolic branch plays within a release train."""

    TEAM = "team"
    INTEGRATION = "integration"
    MAINLINE = "mainline"
    SUPPORT = "support"
    OTHER = "other"


class ReleaseTrainBranch(PychestrateModelBase, SerializableModel):
    """Symbolic branches that define the flow of a release train."""

    __tablename__ = "release_train_branch"

    __table_args__ = (
        UniqueConstraint("rtrain_id", "rtbranch_name", name="uq_release_train_branch"),
    )

    id = Column("rtbranch_id", BigInteger, primary_key=True, autoincrement=True)
    name = Column("rtbranch_name", VARCHAR(128), nullable=False)
    description = Column("rtbranch_description", Text, nullable=True)
    branch_type = Column(
        "rtbranch_type",
        Enum(ReleaseTrainBranchType, name="release_train_branch_type", native_enum=False),
        nullable=False,
        default=ReleaseTrainBranchType.OTHER,
    )
    display_order = Column("rtbranch_display_order", Integer, nullable=False, default=0)
    is_terminal = Column("rtbranch_is_terminal", Boolean, nullable=False, default=False)
    metadata_payload = Column("rtbranch_metadata", JSON, nullable=True)

    release_train_id = Column(
        "rtrain_id", BigInteger, ForeignKey("release_train.rtrain_id"), nullable=False, index=True
    )
    parent_id = Column(
        "parent_rtbranch_id",
        BigInteger,
        ForeignKey("release_train_branch.rtbranch_id"),
        nullable=True,
        index=True,
    )

    train = relationship("ReleaseTrain", back_populates="branches", lazy="selectin")
    parent = relationship(
        "ReleaseTrainBranch",
        remote_side=lambda: [ReleaseTrainBranch.id],
        backref=backref(
            "children",
            lazy="selectin",
            order_by="ReleaseTrainBranch.display_order",
        ),
        lazy="selectin",
    )

    branch_assignments = relationship(
        "ReleaseBranchAssignment",
        back_populates="symbolic_branch",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Release(PychestrateModelBase, SerializableModel):
    """Represents a release of a product built from a release train."""

    __tablename__ = "release"

    __table_args__ = (
        UniqueConstraint("prod_id", "release_name", name="uq_release_product_name"),
    )

    id = Column("release_id", BigInteger, primary_key=True, autoincrement=True)
    name = Column("release_name", VARCHAR(128), nullable=False)
    description = Column("release_description", Text, nullable=True)
    documentation_url = Column("release_documentation_url", VARCHAR(2048), nullable=True)
    start_date = Column("release_start_date", DateTime(timezone=True), nullable=True)
    release_date = Column("release_release_date", DateTime(timezone=True), nullable=True)

    product_id = Column(
        "prod_id", BigInteger, ForeignKey("product.prod_id"), nullable=False, index=True
    )
    release_train_id = Column(
        "rtrain_id", BigInteger, ForeignKey("release_train.rtrain_id"), nullable=True, index=True
    )

    product = relationship("Product", back_populates="releases", lazy="selectin")
    release_train = relationship("ReleaseTrain", back_populates="releases", lazy="selectin")

    branch_assignments = relationship(
        "ReleaseBranchAssignment",
        back_populates="release",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ReleaseBranchAssignment(PychestrateModelBase, SerializableModel):
    """Maps a symbolic release train branch to a literal branch name for a release."""

    __tablename__ = "release_branch_assignment"

    __table_args__ = (
        UniqueConstraint(
            "release_id",
            "rtbranch_id",
            name="uq_release_branch_assignment",
        ),
    )

    id = Column("rba_id", BigInteger, primary_key=True, autoincrement=True)
    literal_branch_name = Column("rba_literal_branch_name", VARCHAR(256), nullable=False)

    release_id = Column(
        "release_id", BigInteger, ForeignKey("release.release_id"), nullable=False, index=True
    )
    release_train_branch_id = Column(
        "rtbranch_id",
        BigInteger,
        ForeignKey("release_train_branch.rtbranch_id"),
        nullable=False,
        index=True,
    )

    release = relationship("Release", back_populates="branch_assignments", lazy="selectin")
    symbolic_branch = relationship("ReleaseTrainBranch", back_populates="branch_assignments", lazy="selectin")


class Repository(PychestrateModelBase, SerializableModel):
    """
        A data modelf for storing repository information.
    """

    __tablename__ = "repository"

    __table_args__ = (UniqueConstraint('repo_name', 'repo_repository', name='uq_repository_name_url'),)

    id = Column('repo_id', BigInteger, primary_key=True, autoincrement=True)
    name = Column('repo_name', VARCHAR(128), nullable=False)
    url = Column('repo_repository', VARCHAR(2048), nullable=False, unique=True)
    repotype = Column('repo_type', Enum(RepositoryType, name='repository_type', native_enum=False), nullable=False)
    scope = Column('repo_scope', Enum(RepositoryScope, name='repository_scope', native_enum=False), nullable=False)
    repoconf = Column('repo_conf', JSON, nullable=False)
    product_links = relationship('ProductToRepository', back_populates='repository', cascade='all, delete-orphan', lazy='selectin')
    components = relationship('ProductComponent', back_populates='repository', lazy='selectin')
    branches = relationship('Branch', back_populates='repository', cascade='all, delete-orphan', lazy='selectin')


class Branch(PychestrateModelBase, SerializableModel):
    """
        A data model for storing source branch information.
    """

    __tablename__ = "branch"

    __table_args__ = (UniqueConstraint('repo_id', 'branch_name', name='uq_branch_repo_name'),)

    id = Column('branch_id', BigInteger, primary_key=True, autoincrement=True)
    name = Column('branch_name', VARCHAR(128), nullable=False)
    owner = Column('branch_owner', VARCHAR(128), nullable=False)

    repo_id = Column('repo_id', BigInteger, ForeignKey('repository.repo_id'), nullable=False, index=True)

    repository = relationship('Repository', back_populates='branches', lazy='selectin')

    build_jobs = relationship('BuildJob', back_populates='branch', cascade='all, delete-orphan', lazy='selectin')
    build_results = relationship('BuildResult', back_populates='branch', cascade='all, delete-orphan', lazy='selectin')


class BuildJob(PychestrateModelBase, SerializableModel):
    """
        A data model for storing build job information.
    """

    __tablename__ = "build_job"

    id = Column('bjob_id', BigInteger, primary_key=True, autoincrement=True)
    name = Column('bjob_name', VARCHAR(128), nullable=False)
    start = Column('bjob_start', DateTime(timezone=True), nullable=False, server_default=func.now())
    stop = Column('bjob_stop', DateTime(timezone=True), nullable=True)
    change = Column('bjob_change', VARCHAR(128), nullable=False)
    status = Column('bjob_status', Enum(WorkPacketStatus, name='build_job_status', native_enum=False), nullable=False, default=WorkPacketStatus.QUEUED)

    branch_id = Column('branch_id', BigInteger, ForeignKey('branch.branch_id'), nullable=False, index=True)

    branch = relationship('Branch', back_populates='build_jobs', lazy='selectin')
    result = relationship('BuildResult', back_populates='job', uselist=False, cascade='all, delete-orphan', lazy='selectin')


class BuildResult(PychestrateModelBase, SerializableModel):
    """
        A data model for storing build information.
    """

    __tablename__ = "build_result"

    id = Column('build_id', BigInteger, primary_key=True, autoincrement=True)
    name = Column('build_name', VARCHAR(128), nullable=False)
    start = Column('build_start', DateTime(timezone=True), nullable=False, server_default=func.now())
    stop = Column('build_stop', DateTime(timezone=True), nullable=True)
    change = Column('build_change', VARCHAR(128), nullable=False)

    branch_id = Column('branch_id', BigInteger, ForeignKey('branch.branch_id'), nullable=False, index=True)
    job_id = Column('bjob_id', BigInteger, ForeignKey('build_job.bjob_id'), nullable=True, index=True)

    branch = relationship('Branch', back_populates='build_results', lazy='selectin')
    job = relationship('BuildJob', back_populates='result', lazy='selectin')

    byproducts = relationship('BuildByProduct', back_populates='build', cascade='all, delete-orphan', lazy='selectin')


class BuildByProduct(PychestrateModelBase, SerializableModel):
    """
        A data mode for linking build byproducts to build
    """
    __tablename__ = "build_byproduct"

    id = Column('bbp_id', BigInteger, primary_key=True, autoincrement=True)
    product = Column('bbp_product', VARCHAR(128), nullable=False)
    arch = Column('bbp_arch', VARCHAR(128), nullable=False)
    buildno = Column('bbp_buildno', VARCHAR(128), nullable=False)
    flavor = Column('bbp_flavor', VARCHAR(128), nullable=False)
    result_url = Column('bbp_result_url', VARCHAR(2048), nullable=False)

    build_id = Column('build_id', BigInteger, ForeignKey('build_result.build_id'), nullable=False, index=True)

    build = relationship('BuildResult', back_populates='byproducts', lazy='selectin')


class User(PychestrateModelBase, SerializableModel):
    """
        A data model for the minimal amount of User information to store
        for relating automation data to an enterprise user.
    """

    __tablename__ = 'user'

    id = Column('user_id', UUIDType, primary_key=True, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    first_name = Column('user_firstName', VARCHAR(40), nullable=False)
    last_name = Column('user_lastName', VARCHAR(40), nullable=False)
    email = Column('user_email', VARCHAR(128), nullable=False, unique=True)
    login = Column('user_login', VARCHAR(128), nullable=False, unique=True)
    ownertag = Column('user_ownertag', VARCHAR(40), nullable=True)

    work_packets = relationship('WorkPacket', back_populates='user', lazy='selectin')

    test_runs = relationship('TestJobRun', back_populates='user', lazy='selectin')

    feature_groups = relationship('FeatureGroupMembership', back_populates='user', lazy='selectin', cascade='all, delete-orphan')


class WorkQueue(PychestrateModelBase, SerializableModel):
    """
        A data model for a
    """
    __tablename__ = 'work_queue'

    id = Column('queue_id', UUIDType, primary_key=True, nullable=False, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    name = Column('queue_name', String(128), nullable=False, unique=True)
    qtype = Column('queue_type', String(128), nullable=False)
    description = Column('queue_desc', TEXT, nullable=False)
    state = Column('queue_state', Enum(WorkQueueState, name='work_queue_state', native_enum=False), nullable=False)

    packets = relationship('WorkPacket', back_populates='queue', cascade='all, delete-orphan', lazy='selectin')


class WorkPacket(PychestrateModelBase, SerializableModel):
    """
        A data model for a WorkPacket(s) and the work items that are part of a work queue.
    """
    __tablename__ = 'work_packet'
    
    id = Column('wkpack_id', BigInteger, primary_key=True, autoincrement=True)

    jtype = Column('wkpk_jtype', Enum(WorkQueueJobType, name='work_queue_job_type', native_enum=False), nullable=False)
    title =  Column('wkpk_title', String(1024), nullable=False)
    description = Column('wkpk_description', Text, nullable=False)
    branch =  Column('wkpk_branch', String(1024), nullable=True)
    build =  Column('wkpk_build', String(1024), nullable=True)
    flavor =  Column('wkpk_flavor', String(1024), nullable=True)
    ownertag = Column('wkpk_ownertag', VARCHAR(40), nullable=True)
    added = Column('wkpk_added', DateTime(timezone=True), nullable=False, server_default=func.now())
    start = Column('wkpk_start', DateTime(timezone=True), nullable=True)
    stop = Column('wkpk_stop', DateTime(timezone=True), nullable=True)
    progress = Column('wkpk_progress', Float, default=0.0)
    status = Column('wkpk_status', Enum(WorkPacketStatus, name='work_packet_status', native_enum=False), nullable=False, index=True)
    packet = Column('wkpk_packet', TEXT, nullable=False)

    queue_id = Column('queue_id',  UUIDType, ForeignKey('work_queue.queue_id'), nullable=False, index=True)
    user_id = Column('user_id', UUIDType, ForeignKey('user.user_id'), nullable=False, index=True)

    queue = relationship('WorkQueue', back_populates='packets', lazy='selectin')

    user = relationship('User', back_populates='work_packets', lazy='selectin')


class FeatureGroup(PychestrateModelBase, SerializableModel):
    """
        A data model for storing information about feature groups.
    """
    __tablename__ = 'feature_group'
    
    id = Column('fg_id', BigInteger, primary_key=True, autoincrement=True)
    name = Column('fg_name', VARCHAR(256), nullable=False)
    description = Column('fg_description', TEXT, nullable=False)

    test_jobs = relationship('TestJob', back_populates='owner_feature_group', lazy='selectin')

    memberships = relationship('FeatureGroupMembership', back_populates='feature_group', cascade='all, delete-orphan', lazy='selectin')

    test_runs = relationship('TestJobRun', back_populates='feature_group', lazy='selectin')


class TestJob(PychestrateModelBase, SerializableModel):
    """
        A data model for storing information about test jobs and
        user and feature group associations with a given test job.
    """
    __tablename__ = 'test_job'

    id = Column('tj_id', UUIDType, primary_key=True, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    title =  Column('tj_title', VARCHAR(1024), nullable=False)
    description = Column('tj_description', Text, nullable=False)

    owner_fg_id = Column('owner_fg_id', BigInteger, ForeignKey('feature_group.fg_id'), nullable=True, index=True)

    owner_feature_group = relationship('FeatureGroup', back_populates='test_jobs', lazy='selectin')

    runs = relationship('TestJobRun', back_populates='job', cascade='all, delete-orphan', lazy='selectin')

    result_containers = relationship('TestResultContainer', back_populates='test_job', cascade='all, delete-orphan', lazy='selectin')


class TestJobRun(PychestrateModelBase, SerializableModel):
    """
        A data model for a TestJob run.
    """

    __tablename__ = 'test_job_run'

    instance = Column('tjr_instance', UUIDType, nullable=False, primary_key=True, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    branch =  Column('tjr_branch', VARCHAR(1024), nullable=True)
    build =  Column('tjr_build', VARCHAR(1024), nullable=True)
    flavor =  Column('tjr_flavor', VARCHAR(1024), nullable=True)
    ownertag = Column('wkpk_ownertag', UUIDType, nullable=True)
    start = Column('tjr_start', DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    stop = Column('tjr_stop', DateTime(timezone=True), nullable=True)
    detail = Column('tjr_detail', JSON, nullable=True)

    job_id = Column('job_id', UUIDType, ForeignKey('test_job.tj_id'), nullable=False, index=True)
    user_id = Column('user_id', UUIDType, ForeignKey('user.user_id'), nullable=False, index=True)

    fg_id = Column('fg_id', BigInteger, ForeignKey('feature_group.fg_id'), nullable=True, index=True)

    job = relationship('TestJob', back_populates='runs', lazy='selectin')

    user = relationship('User', back_populates='test_runs', lazy='selectin')

    feature_group = relationship('FeatureGroup', back_populates='test_runs', lazy='selectin')

    results = relationship('TestResult', back_populates='test_run', cascade='all, delete-orphan', lazy='selectin')


class TestResult(PychestrateModelBase, SerializableModel):
    """
        A data model for a TestResult node that is part of a test result tree.
    """
    __tablename__ = 'test_result'

    instance = Column('tstr_instance', UUIDType, nullable=False, primary_key=True, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    name =  Column('tstr_name', VARCHAR(1024), nullable=False)
    monikers = Column('tstr_monikers', JSON, nullable=True)
    pivots = Column('tstr_pivots', JSON, nullable=True)
    rtype = Column('tstr_rtype', String(50), nullable=False)
    result = Column('tstr_result', String(50), nullable=False)
    start = Column('tstr_start', DateTime(timezone=True), nullable=False, server_default=func.now())
    stop = Column('tstr_stop', DateTime(timezone=True), nullable=True)
    detail = Column('tstr_detail', JSON, nullable=True)

    testrun = Column('tjr_instance', UUIDType, ForeignKey('test_job_run.tjr_instance'), nullable=True, index=True)

    test_run = relationship('TestJobRun', back_populates='results', lazy='selectin')


class TestResultContainer(PychestrateModelBase, SerializableModel):
    """
        A data model for a TestResultContainer node that is part of a test result tree.  The
        TestResultContainer node serves as a parent and container for individual result based
        nodes.
    """
    __tablename__ = 'test_result_container'
    
    id = Column('tstrcont_id', BigInteger, primary_key=True, autoincrement=True)
    name =  Column('tstrcont_name', VARCHAR(1024), nullable=False)
    instance = Column('tstrcont_instance', UUIDType, nullable=False, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    parent = Column('tstrcont_parent', UUIDType, nullable=True)
    rtype = Column('tstrcont_rtype', String(50), nullable=False)

    testjob_id = Column('tj_id', UUIDType, ForeignKey('test_job.tj_id'), index=True)

    test_job = relationship('TestJob', back_populates='result_containers', lazy='selectin')


class FeatureGroupMembership(PychestrateModelBase, SerializableModel):
    """
        A data model for associating FeatureGroup(s) to Users(s)
    """
    __tablename__ = "feature_group_membership"

    fg_id = Column('fg_id', BigInteger, ForeignKey('feature_group.fg_id'), primary_key=True, index=True)
    user_id = Column('user_id', UUIDType, ForeignKey('user.user_id'), primary_key=True, index=True)

    join_date = Column('fgm_join_date', DateTime(timezone=True), nullable=False, server_default=func.now())
    departure_date = Column('fgm_departure_date', DateTime(timezone=True), nullable=True)

    feature_group = relationship('FeatureGroup', back_populates='memberships', lazy='selectin')

    user = relationship('User', back_populates='feature_groups', lazy='selectin')


class OauthUser(PychestrateModelBase, SerializableModel):
    """Represents a user authenticated through an OAuth provider."""

    __tablename__ = "users"

    id = Column('user_id', VARCHAR(40), primary_key=True)

    provider = Column('user_provider', VARCHAR(50), nullable=True, doc="OAuth provider name (google, github, gitlab, microsoft, apple)")
    provider_ref_id = Column('user_provider_ref_id', VARCHAR(255), nullable=False, index=True, doc="Unique identifier from the OAuth provider" \
                             " (sub or id) for the user account")
    firstname = Column('user_firstname', VARCHAR(255), nullable=False, doc="First name of the user, if provided")
    lastname = Column('user_lastname', VARCHAR(255), nullable=False, doc="Last name of the user, if provided")
    display_name = Column('user_display_name', VARCHAR(255), nullable=True, doc="Display name of the user")
    username = Column('user_username', VARCHAR(255), nullable=False, doc="Username of the user, if provided")
    email = Column('user_email', VARCHAR(255), nullable=False, doc="Email address associated with the account")
    avatar_uri = Column('user_avatar_uri', VARCHAR(1024), nullable=True, doc="URI of the user's avatar or profile picture")
    status = Column('user_status', VARCHAR(20), nullable=False, default='active', doc="Status of the user account (e.g., 'active', 'inactive')")
    roles = Column('user_roles', VARCHAR(1024), nullable=True, doc="Comma-separated list of roles assigned to the user (e.g., 'admin,user')")
    authtype = Column('user_authtype', VARCHAR(20), nullable=False, default='consumer', doc="Type of user (e.g., 'internal', 'consumer')")
    created_at = Column('user_created_at', DateTime, default=utc_now, nullable=False, doc="Timestamp when the user record was created")
    updated_at = Column('user_updated_at', DateTime, default=utc_now, onupdate=utc_now, nullable=False, doc="Timestamp when the user record was last updated")
