"""Modelos de dados (SQLAlchemy 2.x, tipos portáveis).

As listas SharePoint da ASAP e da SUPERUS têm colunas diferentes, então cada
empresa tem suas próprias tabelas. O comentário `sp:` indica o nome interno da
coluna original, para rastrear a futura importação dos dados.

Convenções:
- Valores monetários: Numeric(15, 2) — nunca float.
- Números sem semântica monetária (Início/Fim de Medição, Qtd_BMs, FRS, metas):
  Numeric(18, 4), porque o SharePoint os define como "número" sem casas fixas.
- Colunas de escolha do SharePoint viram texto; as opções ficam em config/opcoes.json.
- Anexos: arquivo em disco (pasta de dados) + metadados na tabela `anexos`.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship

# Nomes previsíveis para constraints: facilitam migrações em qualquer banco.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

MONEY = Numeric(15, 2)
NUMBER = Numeric(18, 4)
TEXT255 = String(255)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class AuditMixin:
    """Auditoria técnica do registro (equivale a Created/Modified do SharePoint)."""

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class VersaoMixin:
    """Controle de edição simultânea (bloqueio otimista).

    Cada gravação incrementa `versao` e o UPDATE/DELETE só afeta a linha se a versão no banco
    ainda for a lida; caso contrário o SQLAlchemy levanta StaleDataError (ver services.common).
    """

    versao: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    @declared_attr.directive
    def __mapper_args__(cls) -> dict:
        return {"version_id_col": cls.versao}


class Empresa(Base):
    """Unidade de negócio da holding. Base para futuras permissões por empresa."""

    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(TEXT255, nullable=False)


class Usuario(Base):
    """Conta local do SIM. Senhas são armazenadas somente como hashes."""

    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(
            "perfil IN ('usuario', 'planejador', 'faturamento', 'controle', 'controle_geral')",
            name="perfil_valido",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalizado: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(TEXT255, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    perfil: Mapped[str] = mapped_column(String(30), nullable=False, default="usuario")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deve_trocar_senha: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tentativas_login: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime)
    versao_sessao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ultimo_login_em: Mapped[datetime | None] = mapped_column(DateTime)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    acessos_centros_custo: Mapped[list["AcessoCentroCusto"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )


class DominioPermitido(Base):
    """Domínio autorizado para contas que um administrador provisiona."""

    __tablename__ = "dominios_permitidos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dominio: Mapped[str] = mapped_column(String(253), unique=True, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AcessoCentroCusto(Base):
    """Concessão de acesso a um centro de custo de uma das empresas."""

    __tablename__ = "acessos_centros_custo"
    __table_args__ = (
        CheckConstraint(
            "(asap_centro_custo_id IS NOT NULL AND superus_centro_custo_id IS NULL)"
            " OR (asap_centro_custo_id IS NULL AND superus_centro_custo_id IS NOT NULL)",
            name="um_centro_custo",
        ),
        CheckConstraint(
            "empresa_id > 0",
            name="empresa_positiva",
        ),
        UniqueConstraint("usuario_id", "asap_centro_custo_id", name="uq_acesso_usuario_asap_cc"),
        UniqueConstraint("usuario_id", "superus_centro_custo_id", name="uq_acesso_usuario_superus_cc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False)
    asap_centro_custo_id: Mapped[int | None] = mapped_column(
        ForeignKey("asap_centros_custo.id", ondelete="CASCADE")
    )
    superus_centro_custo_id: Mapped[int | None] = mapped_column(
        ForeignKey("superus_centros_custo.id", ondelete="CASCADE")
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    usuario: Mapped[Usuario] = relationship(back_populates="acessos_centros_custo")
    empresa: Mapped[Empresa] = relationship()
    asap_centro_custo: Mapped[AsapCentroCusto | None] = relationship()
    superus_centro_custo: Mapped[SuperusCentroCusto | None] = relationship()


class AuditoriaAcesso(Base):
    """Auditoria de alterações administrativas de contas e permissões."""

    __tablename__ = "auditoria_acessos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ator_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    alvo_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    acao: Mapped[str] = mapped_column(String(60), nullable=False)
    detalhes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)


class CodigoRedefinicaoSenha(Base):
    """Código enviado por e-mail para redefinir a senha. Guardado só como hash."""

    __tablename__ = "codigos_redefinicao_senha"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codigo_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usado_em: Mapped[datetime | None] = mapped_column(DateTime)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class SolicitacaoAcesso(Base):
    """Pedido de conta feito na tela de login, aguardando decisão de um aprovador.

    A senha escolhida pelo solicitante fica só como hash e é apagada da solicitação
    quando ela é decidida (na aprovação, o hash passa para a conta criada).
    """

    __tablename__ = "solicitacoes_acesso"
    __table_args__ = (
        CheckConstraint(
            "perfil_solicitado IN ('usuario', 'planejador', 'faturamento', 'controle', 'controle_geral')",
            name="perfil_valido",
        ),
        CheckConstraint("status IN ('pendente', 'aprovada', 'recusada')", name="status_valido"),
        # Um pedido em aberto por e-mail, garantido pelo banco mesmo com envios simultâneos.
        Index(
            "uq_solicitacoes_acesso_pendente", "email_normalizado", unique=True,
            sqlite_where=text("status = 'pendente'"), postgresql_where=text("status = 'pendente'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(TEXT255, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalizado: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    senha_hash: Mapped[str | None] = mapped_column(String(255))
    perfil_solicitado: Mapped[str] = mapped_column(String(30), nullable=False)
    # Texto livre digitado pelo solicitante; serve de referência para o aprovador.
    centro_custo_informado: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente", index=True)
    parecer: Mapped[str | None] = mapped_column(Text)
    decidido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


# ---------------------------------------------------------------- ASAP ----


class AsapCentroCusto(AuditMixin, VersaoMixin, Base):
    """Lista SharePoint 'Lista de Apoio ASAP'."""

    __tablename__ = "asap_centros_custo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False)
    titulo: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: Title
    # Título normalizado (sem espaços extras, minúsculo) para impedir duplicidade.
    titulo_chave: Mapped[str] = mapped_column(TEXT255, nullable=False, unique=True)
    cliente: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: Cliente
    numero_contrato: Mapped[str | None] = mapped_column(TEXT255)  # sp: NºdoContrato
    cidade: Mapped[str | None] = mapped_column(TEXT255)  # sp: Cidade (escolha)
    inicio_medicao: Mapped[Decimal] = mapped_column(NUMBER, nullable=False)  # sp: IníciodeMedição
    fim_medicao: Mapped[Decimal] = mapped_column(NUMBER, nullable=False)  # sp: FimdeMedição
    email: Mapped[str] = mapped_column(Text, nullable=False)  # sp: E-mail (multilinha)
    meta_bm: Mapped[Decimal | None] = mapped_column(NUMBER)  # sp: MetaBM
    periodo: Mapped[str | None] = mapped_column(TEXT255)  # sp: p ("Mensal ou Quinzenal")
    # Encerramento: CC inativo não aceita novos BMs (ver EncerramentoCentroCusto).
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())

    bms: Mapped[list["AsapBM"]] = relationship(back_populates="centro_custo")


class AsapBM(AuditMixin, VersaoMixin, Base):
    """Lista SharePoint 'BMs ASAP'."""

    __tablename__ = "asap_bms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    centro_custo_id: Mapped[int] = mapped_column(
        ForeignKey("asap_centros_custo.id", ondelete="RESTRICT"), nullable=False, index=True
    )  # sp: CentrodeCusto (lookup)
    titulo: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: Title ("Nome do Arquivo")
    ano: Mapped[str] = mapped_column(String(20), nullable=False)  # sp: Ano (escolha)
    mes_referencia: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # sp: MêsdeReferência
    status: Mapped[str] = mapped_column(TEXT255, nullable=False, index=True)  # sp: Status
    valor_bm: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # sp: ValorBM
    valor_aprovado: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # sp: ValorAprovado
    valor_emitido: Mapped[Decimal | None] = mapped_column(MONEY)  # sp: ValorEmitido
    glosa: Mapped[Decimal | None] = mapped_column(MONEY)  # sp: Glosa
    frs: Mapped[Decimal | None] = mapped_column(NUMBER)  # sp: FRS
    valor_liberado: Mapped[Decimal | None] = mapped_column(MONEY)  # sp: ValorLiberado
    observacoes: Mapped[str | None] = mapped_column(Text)  # sp: Observações
    data_aprovacao_cliente: Mapped[datetime | None] = mapped_column(DateTime)  # sp: DataAprovacaoCliente
    ultimo_alerta: Mapped[datetime | None] = mapped_column(DateTime)  # sp: UltimoAlerta (fluxo externo)
    data_criacao: Mapped[datetime | None] = mapped_column(DateTime)  # sp: DataCriação (coluna editável)

    centro_custo: Mapped[AsapCentroCusto] = relationship(back_populates="bms")
    anexos: Mapped[list["Anexo"]] = relationship(
        back_populates="asap_bm", cascade="all, delete-orphan", passive_deletes=True
    )


# ------------------------------------------------------------- SUPERUS ----


class SuperusCentroCusto(AuditMixin, VersaoMixin, Base):
    """Lista SharePoint 'Lista de Apoio' (SUPERUS)."""

    __tablename__ = "superus_centros_custo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False)
    titulo: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: Title (código do CC)
    titulo_chave: Mapped[str] = mapped_column(TEXT255, nullable=False, unique=True)
    obra_cliente: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: Obra_x002f_Cliente
    gestor_obra: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: GestordeObra
    coligada: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: Coligada
    numero_contrato: Mapped[str | None] = mapped_column(TEXT255)  # sp: NºdoContrato
    cidade: Mapped[str | None] = mapped_column(TEXT255)  # sp: Cidade (texto)
    inicio_medicao: Mapped[Decimal] = mapped_column(NUMBER, nullable=False)  # sp: IniciodeMedição
    fim_medicao: Mapped[Decimal] = mapped_column(NUMBER, nullable=False)  # sp: FimdeMedição
    meta_bm: Mapped[Decimal | None] = mapped_column(NUMBER)  # sp: MetaBM
    meta_frs: Mapped[Decimal | None] = mapped_column(NUMBER)  # sp: MetaFRS
    novo_prazo: Mapped[bool | None] = mapped_column(Boolean)  # sp: Novoprazo
    competencia_emissao: Mapped[str | None] = mapped_column(TEXT255)  # sp: CompetênciadeEmissão (escolha)
    email_gestor: Mapped[str | None] = mapped_column(TEXT255)  # sp: Email
    email_gerente: Mapped[str | None] = mapped_column(TEXT255)  # sp: EmailGerente
    gerente: Mapped[str | None] = mapped_column(TEXT255)  # sp: Gerente
    status_cobranca: Mapped[str | None] = mapped_column(TEXT255)  # sp: StatusCobrança
    encerramento_manual: Mapped[str | None] = mapped_column(TEXT255)  # sp: EncerramentoManual (escolha)
    qtd_bms: Mapped[Decimal | None] = mapped_column(NUMBER)  # sp: Qtd_BMs
    mes_apuracao: Mapped[date | None] = mapped_column(Date)  # sp: MêsdeApuração
    motivo_encerramento: Mapped[str | None] = mapped_column(Text)  # sp: MotivoEncerramento
    # Encerramento: CC inativo não aceita novos BMs (ver EncerramentoCentroCusto).
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())

    bms_mensais: Mapped[list["SuperusBMMensal"]] = relationship(back_populates="centro_custo")
    bms_semanais: Mapped[list["SuperusBMSemanal"]] = relationship(back_populates="centro_custo")
    valores_previstos: Mapped[list["SuperusValorPrevisto"]] = relationship(
        back_populates="centro_custo", cascade="all, delete-orphan", passive_deletes=True
    )


class SuperusBMMensal(AuditMixin, VersaoMixin, Base):
    """Lista SharePoint 'BMs' (SUPERUS)."""

    __tablename__ = "superus_bms_mensais"
    __table_args__ = (
        # Uma resposta por CC e mês. Só para BMs do SIM novo: o histórico importado tem meses repetidos
        # (o serviço também recusa um BM novo num mês já ocupado por um BM do histórico).
        Index(
            "uq_superus_bm_mensal_mes", "centro_custo_id", "ano", "mes_referencia", unique=True,
            sqlite_where=text("id_legado IS NULL"), postgresql_where=text("id_legado IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    centro_custo_id: Mapped[int] = mapped_column(
        ForeignKey("superus_centros_custo.id", ondelete="RESTRICT"), nullable=False, index=True
    )  # sp: Integração (lookup)
    titulo: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: Title ("Nome do Arquivo")
    numero_contrato: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: NºdoContrato
    cidade: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: Cidade ("Cidade do Serviço")
    ano: Mapped[str] = mapped_column(String(20), nullable=False)  # sp: Ano
    mes_referencia: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # sp: MêsdeReferência
    tipo: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: Tipo1 ("BM ou PO?")
    status: Mapped[str] = mapped_column(TEXT255, nullable=False, index=True)  # sp: Status
    valor_bm: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # sp: ValorBM ("Valor BM/PO")
    glosa: Mapped[Decimal | None] = mapped_column(MONEY)  # sp: Glosa
    postergado: Mapped[Decimal | None] = mapped_column(MONEY)  # sp: Postergado
    valor_aprovado: Mapped[Decimal | None] = mapped_column(MONEY)  # sp: ValorAprovado
    valor_liberado: Mapped[Decimal | None] = mapped_column(MONEY)  # sp: ValorLiberado
    valor_emitido: Mapped[Decimal | None] = mapped_column(MONEY)  # sp: ValorEmitido
    frs: Mapped[Decimal | None] = mapped_column(NUMBER)  # sp: FRS
    po: Mapped[str | None] = mapped_column(TEXT255, index=True)  # sp: PO
    prazo_envio_bm: Mapped[date | None] = mapped_column(Date)  # sp: PrazoEnvioBM
    prazo_liberacao_frs: Mapped[date | None] = mapped_column(Date)  # sp: PrazoLiberaçãoFRS
    data_faturamento: Mapped[date | None] = mapped_column(Date)  # sp: DatadeFaturamento
    # ID do item na lista SharePoint, quando o BM veio da importação do histórico (sim/importacao_legado.py).
    id_legado: Mapped[int | None] = mapped_column(Integer, unique=True)
    # Valor previsto do mês no momento do lançamento e a explicação exigida quando o BM foge mais de 5% dele
    # (sim/services/previsto.py).
    valor_previsto: Mapped[Decimal | None] = mapped_column(MONEY)
    justificativa_variacao: Mapped[str | None] = mapped_column(Text)

    centro_custo: Mapped[SuperusCentroCusto] = relationship(back_populates="bms_mensais")
    anexos: Mapped[list["Anexo"]] = relationship(
        back_populates="superus_bm_mensal", cascade="all, delete-orphan", passive_deletes=True
    )
    # BMs que compõem a resposta do mês; valor_bm e valor_aprovado são as somas deles. BMs do histórico não têm.
    itens: Mapped[list["SuperusBMMensalItem"]] = relationship(
        back_populates="bm", cascade="all, delete-orphan", passive_deletes=True,
        order_by="SuperusBMMensalItem.ordem",
    )


class SuperusBMMensalItem(Base):
    """Um BM dentro da resposta mensal (o gestor lança BM por BM e o SIM soma)."""

    __tablename__ = "superus_bm_mensal_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bm_id: Mapped[int] = mapped_column(
        ForeignKey("superus_bms_mensais.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    descricao: Mapped[str] = mapped_column(TEXT255, nullable=False)  # identificação do BM (nº, escopo)
    valor_bm: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    valor_aprovado: Mapped[Decimal | None] = mapped_column(MONEY)

    bm: Mapped[SuperusBMMensal] = relationship(back_populates="itens")


class SuperusValorPrevisto(AuditMixin, Base):
    """Lista SharePoint 'Valor Previsto' (SUPERUS): quanto se espera medir no mês, por centro de custo.

    Preenchido pelo Controle no Administrativo e mostrado ao gestor no lançamento do BM mensal.
    """

    __tablename__ = "superus_valores_previstos"
    __table_args__ = (UniqueConstraint("centro_custo_id", "ano", "mes_referencia", name="uq_valor_previsto_cc_mes"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    centro_custo_id: Mapped[int] = mapped_column(
        ForeignKey("superus_centros_custo.id", ondelete="CASCADE"), nullable=False, index=True
    )  # sp: Title (código do CC)
    ano: Mapped[str] = mapped_column(String(20), nullable=False)
    mes_referencia: Mapped[str] = mapped_column(String(40), nullable=False)  # sp: MêsdeReferência
    valor: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # sp: ValorPrevisto

    centro_custo: Mapped[SuperusCentroCusto] = relationship(back_populates="valores_previstos")


class SuperusBMSemanal(AuditMixin, VersaoMixin, Base):
    """Lista SharePoint 'BM Semanal' (SUPERUS). Não tem Status no original."""

    __tablename__ = "superus_bms_semanais"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    centro_custo_id: Mapped[int] = mapped_column(
        ForeignKey("superus_centros_custo.id", ondelete="RESTRICT"), nullable=False, index=True
    )  # sp: Integração2 (lookup)
    titulo: Mapped[str] = mapped_column(TEXT255, nullable=False)  # sp: Title
    mes_referencia: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    semana: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # sp: Semana
    valor_bm: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # sp: ValordoBM ("Valor Acumulado do BM")
    id_legado: Mapped[int | None] = mapped_column(Integer, unique=True)  # ID SharePoint (importação do histórico)

    centro_custo: Mapped[SuperusCentroCusto] = relationship(back_populates="bms_semanais")
    anexos: Mapped[list["Anexo"]] = relationship(
        back_populates="superus_bm_semanal", cascade="all, delete-orphan", passive_deletes=True
    )


# -------------------------------------------------------------- ANEXOS ----


class AnexoConteudo(Base):
    """Conteúdo do anexo quando SIM_ANEXOS_BACKEND=banco (hospedagem sem disco persistente)."""

    __tablename__ = "anexos_conteudo"

    caminho_relativo: Mapped[str] = mapped_column(String(500), primary_key=True)
    conteudo: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Anexo(Base):
    """Metadados de um arquivo anexado. O conteúdo fica em disco (SIM_ANEXOS_DIR).

    Cada anexo pertence a exatamente um registro (garantido pela CheckConstraint).
    """

    __tablename__ = "anexos"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN asap_bm_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN superus_bm_mensal_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN superus_bm_semanal_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="um_dono",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asap_bm_id: Mapped[int | None] = mapped_column(ForeignKey("asap_bms.id", ondelete="CASCADE"), index=True)
    superus_bm_mensal_id: Mapped[int | None] = mapped_column(
        ForeignKey("superus_bms_mensais.id", ondelete="CASCADE"), index=True
    )
    superus_bm_semanal_id: Mapped[int | None] = mapped_column(
        ForeignKey("superus_bms_semanais.id", ondelete="CASCADE"), index=True
    )
    nome_original: Mapped[str] = mapped_column(TEXT255, nullable=False)
    caminho_relativo: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_mime: Mapped[str | None] = mapped_column(String(150))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    asap_bm: Mapped[AsapBM | None] = relationship(back_populates="anexos")
    superus_bm_mensal: Mapped[SuperusBMMensal | None] = relationship(back_populates="anexos")
    superus_bm_semanal: Mapped[SuperusBMSemanal | None] = relationship(back_populates="anexos")


# -------------------------------------------------------- encerramento ----


class EncerramentoCentroCusto(Base):
    """Solicitações e registros de encerramento/reativação de centro de custo (ASAP ou SUPERUS).

    Usuário de obra cria um pedido 'pendente' de encerramento, com justificativa; controlador
    Controle ou Controle Geral aprova ou recusa. Ações diretas desses perfis (encerrar pelo
    formulário ou pelo checkbox Ativo, reativar) entram já como 'aprovada', formando o histórico.
    """

    __tablename__ = "encerramentos_cc"
    __table_args__ = (
        CheckConstraint(
            "(asap_cc_id IS NOT NULL AND superus_cc_id IS NULL)"
            " OR (asap_cc_id IS NULL AND superus_cc_id IS NOT NULL)",
            name="um_centro_custo",
        ),
        CheckConstraint("acao IN ('encerrar', 'reativar')", name="acao_valida"),
        CheckConstraint("status IN ('pendente', 'aprovada', 'recusada')", name="status_valido"),
        # Um pedido pendente por centro de custo, garantido pelo banco mesmo com cliques simultâneos.
        Index(
            "uq_encerramentos_cc_asap_pendente", "asap_cc_id", unique=True,
            sqlite_where=text("status = 'pendente'"), postgresql_where=text("status = 'pendente'"),
        ),
        Index(
            "uq_encerramentos_cc_superus_pendente", "superus_cc_id", unique=True,
            sqlite_where=text("status = 'pendente'"), postgresql_where=text("status = 'pendente'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False)
    asap_cc_id: Mapped[int | None] = mapped_column(
        ForeignKey("asap_centros_custo.id", ondelete="CASCADE"), index=True
    )
    superus_cc_id: Mapped[int | None] = mapped_column(
        ForeignKey("superus_centros_custo.id", ondelete="CASCADE"), index=True
    )
    acao: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    justificativa: Mapped[str | None] = mapped_column(Text)
    parecer: Mapped[str | None] = mapped_column(Text)
    solicitante_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    decidido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    empresa: Mapped[Empresa] = relationship()
    asap_centro_custo: Mapped[AsapCentroCusto | None] = relationship()
    superus_centro_custo: Mapped[SuperusCentroCusto | None] = relationship()
    solicitante: Mapped[Usuario | None] = relationship(foreign_keys=[solicitante_id])
    decidido_por: Mapped[Usuario | None] = relationship(foreign_keys=[decidido_por_id])

    @property
    def centro_custo(self):
        return self.asap_centro_custo or self.superus_centro_custo
