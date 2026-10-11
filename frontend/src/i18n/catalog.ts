// Order: Russian, English, Spanish, Brazilian Portuguese, Simplified Chinese, French, German.
// Canonical UI keys are separate from all registry IDs and serialized recipe fields.
export const LOCALES = ["ru", "en", "es", "pt-BR", "zh-Hans", "fr", "de"] as const;
export type Locale = typeof LOCALES[number];
export const LOCALE_NAMES: Record<Locale, string> = {
  ru: "Русский", en: "English", es: "Español", "pt-BR": "Português (Brasil)",
  "zh-Hans": "简体中文", fr: "Français", de: "Deutsch",
};

// This compact source table is intentionally reviewed as a single seven-language catalog.
// Empty community-language cells fall back to English; coverage is computed, never inferred.
const rows = `
nav.components|Компоненты|Components|Componentes|Componentes|组件|Composants|Komponenten
nav.assets|Ассеты|Assets|Recursos|Assets|资产|Ressources|Assets
nav.materials|Материалы|Materials|Materiales|Materiais|材质|Matériaux|Materialien
nav.characters|Персонажи|Characters|Personajes|Personagens|角色|Personnages|Charaktere
nav.sections|Разделы реестра|Registry sections|Secciones del registro|Seções do registro|注册表分区|Sections du registre|Registry-Bereiche
nav.language|Язык интерфейса|Interface language|Idioma de la interfaz|Idioma da interface|界面语言|Langue de l’interface|Sprache der Oberfläche
nav.guide|Руководство|Guide|Guía|Guia|指南|Guide|Anleitung
nav.theme|Тема|Theme|Tema|Tema|主题|Thème|Design
nav.themeHint|светлая / тёмная тема|Light / dark theme|Tema claro / oscuro|Tema claro / escuro|浅色／深色主题|Thème clair / sombre|Helles / dunkles Design
nav.skip|К содержимому|Skip to content|Ir al contenido|Ir para o conteúdo|跳转到内容|Aller au contenu|Zum Inhalt springen
nav.backRegistry|← в реестр|← Back to registry|← Volver al registro|← Voltar ao registro|← 返回注册表|← Retour au registre|← Zurück zur Registry
common.loading|Загрузка…|Loading…|Cargando…|Carregando…|正在加载…|Chargement…|Wird geladen…
common.retry|Повторить|Retry|Reintentar|Tentar novamente|重试|Réessayer|Erneut versuchen
common.reload|Повторить загрузку|Reload|Volver a cargar|Recarregar|重新加载|Recharger|Neu laden
common.close|Закрыть|Close|Cerrar|Fechar|关闭|Fermer|Schließen
common.closeDialog|Закрыть окно|Close dialog|Cerrar ventana|Fechar janela|关闭对话框|Fermer la fenêtre|Dialog schließen
common.cancel|Отмена|Cancel|Cancelar|Cancelar|取消|Annuler|Abbrechen
common.save|Сохранить|Save|Guardar|Salvar|保存|Enregistrer|Speichern
common.saving|Сохранение…|Saving…|Guardando…|Salvando…|正在保存…|Enregistrement…|Wird gespeichert…
common.add|Добавить|Add|Añadir|Adicionar|添加|Ajouter|Hinzufügen
common.remove|Убрать|Remove|Quitar|Remover|移除|Retirer|Entfernen
common.refresh|Обновить|Refresh|Actualizar|Atualizar|刷新|Actualiser|Aktualisieren
common.reset|Сбросить|Reset|Restablecer|Redefinir|重置|Réinitialiser|Zurücksetzen
common.all|Все|All|Todos|Todos|全部|Tous|Alle
common.any|любой|Any|Cualquiera|Qualquer|任意|Tous|Beliebig
common.yes|да|Yes|Sí|Sim|是|Oui|Ja
common.no|нет|No|No|Não|否|Non|Nein
common.empty|пусто|Empty|Vacío|Vazio|空|Vide|Leer
common.description|Описание|Description|Descripción|Descrição|说明|Description|Beschreibung
common.name|Название|Name|Nombre|Nome|名称|Nom|Name
common.level|Уровень|Level|Nivel|Nível|级别|Niveau|Stufe
common.note|заметка|Note|Nota|Nota|备注|Note|Notiz
common.tags|теги|Tags|Etiquetas|Tags|标签|Étiquettes|Tags
common.ready|Готово|Ready|Listo|Pronto|已就绪|Prêt|Bereit
common.noChanges|без изменений|No changes|Sin cambios|Sem alterações|无更改|Aucune modification|Keine Änderungen
common.nothingChanged|ничего не изменено|Nothing changed|No hay cambios|Nada foi alterado|尚未更改|Rien n’a changé|Nichts geändert
common.noPreview|Нет превью|No preview|Sin vista previa|Sem prévia|无预览|Aucun aperçu|Keine Vorschau
common.noResults|Ничего не найдено|No results|Sin resultados|Nenhum resultado|未找到结果|Aucun résultat|Keine Ergebnisse
common.default|по умолчанию|Default|Por defecto|Padrão|默认|Par défaut|Standard
common.up|Выше|Up|Arriba|Acima|上移|Monter|Nach oben
common.down|Ниже|Down|Abajo|Abaixo|下移|Descendre|Nach unten
common.show|Показать|Show|Mostrar|Mostrar|显示|Afficher|Anzeigen
common.hide|Скрыть|Hide|Ocultar|Ocultar|隐藏|Masquer|Ausblenden
status.draft|черновик|Draft|Borrador|Rascunho|草稿|Brouillon|Entwurf
status.built|собран|Built|Generado|Gerado|已构建|Généré|Erstellt
status.failed|ошибка|Failed|Error|Falha|失败|Échec|Fehler
status.approved|одобрен|Approved|Aprobado|Aprovado|已批准|Approuvé|Freigegeben
status.archived|архив|Archived|Archivado|Arquivado|已归档|Archivé|Archiviert
status.queued|в очереди|Queued|En cola|Na fila|排队中|En attente|In Warteschlange
status.running|сборка…|Building…|Generando…|Gerando…|正在构建…|Génération…|Wird erstellt…
build.events|события сборки (SSE)|Build events (SSE)|Eventos de generación (SSE)|Eventos de geração (SSE)|构建事件（SSE）|Événements de génération (SSE)|Build-Ereignisse (SSE)
build.connected|SSE подключён|SSE connected|SSE conectado|SSE conectado|SSE 已连接|SSE connecté|SSE verbunden
build.reconnecting|SSE переподключается…|SSE reconnecting…|Reconectando SSE…|Reconectando SSE…|SSE 正在重新连接…|Reconnexion SSE…|SSE verbindet erneut…
build.queue|сборок в работе: {count}|Active builds: {count}|Generaciones activas: {count}|Gerações ativas: {count}|正在构建：{count}|Générations actives : {count}|Aktive Builds: {count}
build.build|Собрать|Build|Generar|Gerar|构建|Générer|Erstellen
build.rebuild|Пересобрать|Rebuild|Volver a generar|Gerar novamente|重新构建|Regénérer|Neu erstellen
build.create|Создать и собрать|Create and build|Crear y generar|Criar e gerar|创建并构建|Créer et générer|Erstellen und bauen
build.need|Нужна сборка|Build required|Requiere generación|Geração necessária|需要构建|Génération requise|Build erforderlich
build.failure|Ошибка сборки|Build failed|Error de generación|Falha na geração|构建失败|Échec de génération|Build fehlgeschlagen
build.recipeFailure|Ошибка рецепта|Recipe error|Error de receta|Erro na receita|配方错误|Erreur de recette|Rezeptfehler
build.noModel|Модель ещё не собрана|Model has not been built|El modelo aún no se ha generado|O modelo ainda não foi gerado|模型尚未构建|Le modèle n’est pas encore généré|Modell noch nicht erstellt
build.noBuiltModel|Нет собранной модели|No built model|No hay modelo generado|Nenhum modelo gerado|无已构建模型|Aucun modèle généré|Kein erstelltes Modell
build.queued|Сборка в очереди…|Build queued…|Generación en cola…|Geração na fila…|构建已排队…|Génération en attente…|Build in Warteschlange…
build.rebuilding|Идёт пересборка…|Rebuilding…|Volviendo a generar…|Gerando novamente…|正在重新构建…|Regénération…|Wird neu erstellt…
build.sending|Отправка…|Submitting…|Enviando…|Enviando…|正在提交…|Envoi…|Wird gesendet…
build.starting|Запускаю…|Starting…|Iniciando…|Iniciando…|正在启动…|Démarrage…|Wird gestartet…
build.never|Ещё не собирался.|Not built yet.|Aún no generado.|Ainda não foi gerado.|尚未构建。|Pas encore généré.|Noch nicht erstellt.
build.invalid|Рецепт невалиден|Invalid recipe|Receta no válida|Receita inválida|配方无效|Recette invalide|Ungültiges Rezept
build.successFirst|сначала успешная сборка|A successful build is required first|Primero se requiere una generación correcta|É necessária uma geração bem-sucedida primeiro|需要先成功构建|Une génération réussie est requise|Zuerst erfolgreich erstellen
error.offline|Нет связи с сервером. Проверьте, что реестр запущен, и повторите действие.|Cannot reach the server. Check that the registry is running and retry.|No se puede conectar con el servidor. Comprueba que el registro esté iniciado y reintenta.|Não foi possível conectar ao servidor. Verifique se o registro está em execução e tente novamente.|无法连接服务器。请确认注册表正在运行，然后重试。|Serveur inaccessible. Vérifiez que le registre est lancé et réessayez.|Server nicht erreichbar. Prüfen Sie, ob die Registry läuft, und versuchen Sie es erneut.
error.page|Не удалось открыть страницу|Could not open this page|No se pudo abrir la página|Não foi possível abrir a página|无法打开页面|Impossible d’ouvrir cette page|Seite konnte nicht geöffnet werden
error.route|Такого раздела нет. Вернитесь в реестр.|This section does not exist. Return to the registry.|Esta sección no existe. Vuelve al registro.|Esta seção não existe. Volte ao registro.|此分区不存在。请返回注册表。|Cette section n’existe pas. Revenez au registre.|Dieser Bereich existiert nicht. Zurück zur Registry.
error.server|Ошибка сервера ({status}). Повторите действие.|Server error ({status}). Please retry.|Error del servidor ({status}). Reintenta.|Erro do servidor ({status}). Tente novamente.|服务器错误（{status}）。请重试。|Erreur du serveur ({status}). Réessayez.|Serverfehler ({status}). Erneut versuchen.
error.number|Введите число для {name}.|Enter a number for {name}.|Introduce un número para {name}.|Insira um número para {name}.|请输入 {name} 的数值。|Saisissez un nombre pour {name}.|Zahl für {name} eingeben.
catalog.view|Отображение каталога|Catalog view|Vista del catálogo|Visualização do catálogo|目录视图|Vue du catalogue|Katalogansicht
catalog.reset|Сбросить фильтры|Reset filters|Restablecer filtros|Redefinir filtros|重置筛选条件|Réinitialiser les filtres|Filter zurücksetzen
catalog.searchPlaceholder|Название, ID или тег…|Name, ID or tag…|Nombre, ID o etiqueta…|Nome, ID ou tag…|名称、ID 或标签…|Nom, ID ou étiquette…|Name, ID oder Tag…
catalog.search|Поиск в каталоге|Search catalog|Buscar en el catálogo|Buscar no catálogo|搜索目录|Rechercher dans le catalogue|Katalog durchsuchen
catalog.group|Группа|Group|Grupo|Grupo|分组|Groupe|Gruppe
catalog.ungrouped|Без группы|Ungrouped|Sin grupo|Sem grupo|未分组|Sans groupe|Ohne Gruppe
catalog.list|Список|List|Lista|Lista|列表|Liste|Liste
catalog.cards|Карточки|Cards|Tarjetas|Cartões|卡片|Cartes|Karten
catalog.collapseTags|Свернуть теги|Collapse tags|Contraer etiquetas|Recolher tags|收起标签|Réduire les étiquettes|Tags einklappen
catalog.matchAll|Показаны записи со всеми выбранными тегами.|Showing entries with all selected tags.|Se muestran las entradas con todas las etiquetas seleccionadas.|Mostrando entradas com todas as tags selecionadas.|显示包含所有选中标签的条目。|Affichage des entrées avec toutes les étiquettes sélectionnées.|Einträge mit allen ausgewählten Tags werden angezeigt.
catalog.empty|В этом разделе пока нет записей|No entries in this section yet|Esta sección aún no tiene entradas|Ainda não há entradas nesta seção|此分区暂无条目|Aucune entrée dans cette section|Noch keine Einträge in diesem Bereich
catalog.tryFilters|Попробуйте другое название или снимите часть фильтров.|Try another name or remove some filters.|Prueba otro nombre o quita algunos filtros.|Tente outro nome ou remova alguns filtros.|请尝试其他名称或移除部分筛选条件。|Essayez un autre nom ou retirez des filtres.|Anderen Namen versuchen oder einige Filter entfernen.
catalog.type|Тип|Type|Tipo|Tipo|类型|Type|Typ
catalog.preview|Превью|Preview|Vista previa|Prévia|预览|Aperçu|Vorschau
catalog.priority|Важные теги|Priority tags|Etiquetas prioritarias|Tags prioritárias|优先标签|Étiquettes prioritaires|Wichtige Tags
catalog.addAsset|+ Создать ассет|+ Create asset|+ Crear recurso|+ Criar asset|+ 创建资产|+ Créer une ressource|+ Asset erstellen
catalog.manageGroups|Организовать группы|Organize groups|Organizar grupos|Organizar grupos|管理分组|Organiser les groupes|Gruppen organisieren
catalog.table|Обзор на столе|Table overview|Vista en mesa|Visão na mesa|桌面总览|Vue sur table|Tischübersicht
tags.title|Теги|Tags|Etiquetas|Tags|标签|Étiquettes|Tags
tags.search|Найти тег…|Find a tag…|Buscar etiqueta…|Buscar tag…|查找标签…|Trouver une étiquette…|Tag suchen…
tags.searchLabel|Поиск тега|Search tags|Buscar etiquetas|Buscar tags|搜索标签|Rechercher des étiquettes|Tags durchsuchen
tags.manage|Управление тегами|Manage tags|Gestionar etiquetas|Gerenciar tags|管理标签|Gérer les étiquettes|Tags verwalten
tags.input|теги через запятую|Comma-separated tags|Etiquetas separadas por comas|Tags separadas por vírgulas|以逗号分隔的标签|Étiquettes séparées par des virgules|Tags durch Kommas trennen
tags.newName|Новое имя тега|New tag name|Nuevo nombre de etiqueta|Novo nome da tag|新标签名称|Nouveau nom d’étiquette|Neuer Tag-Name
tags.name|Имя тега|Tag name|Nombre de etiqueta|Nome da tag|标签名称|Nom d’étiquette|Tag-Name
tags.delete|Удалить тег|Delete tag|Eliminar etiqueta|Excluir tag|删除标签|Supprimer l’étiquette|Tag löschen
tags.deleting|Удаление…|Deleting…|Eliminando…|Excluindo…|正在删除…|Suppression…|Wird gelöscht…
tags.deleteAll|Удалить у всех|Remove from all|Quitar de todos|Remover de todos|从全部移除|Retirer partout|Überall entfernen
tags.saveAll|Сохранить для всех|Save for all|Guardar para todos|Salvar para todos|保存到全部|Enregistrer partout|Für alle speichern
tags.noTags|В реестре пока нет тегов.|No tags in the registry yet.|El registro aún no tiene etiquetas.|O registro ainda não tem tags.|注册表暂无标签。|Aucune étiquette dans le registre.|Noch keine Tags in der Registry.
tags.notFound|Тег не найден.|Tag not found.|Etiqueta no encontrada.|Tag não encontrada.|未找到标签。|Étiquette introuvable.|Tag nicht gefunden.
entity.variants|Варианты|Variants|Variantes|Variantes|变体|Variantes|Varianten
entity.noVariants|Вариантов пока нет.|No variants yet.|Aún no hay variantes.|Ainda não há variantes.|暂无变体。|Aucune variante.|Noch keine Varianten.
entity.selectVariant|Выберите вариант в дереве.|Select a variant in the tree.|Selecciona una variante en el árbol.|Selecione uma variante na árvore.|请在树中选择变体。|Sélectionnez une variante dans l’arbre.|Eine Variante im Baum auswählen.
entity.loadingVariant|Загрузка варианта…|Loading variant…|Cargando variante…|Carregando variante…|正在加载变体…|Chargement de la variante…|Variante wird geladen…
entity.branch|Ветка отсюда|Branch from here|Crear rama desde aquí|Criar ramificação daqui|从此处创建分支|Créer une branche ici|Von hier verzweigen
entity.approve|Одобрить|Approve|Aprobar|Aprovar|批准|Approuver|Freigeben
entity.unapprove|Снять одобрение|Remove approval|Retirar aprobación|Remover aprovação|撤销批准|Retirer l’approbation|Freigabe entfernen
entity.archive|В архив|Archive|Archivar|Arquivar|归档|Archiver|Archivieren
entity.unarchive|Из архива|Restore from archive|Restaurar del archivo|Restaurar do arquivo|从归档恢复|Restaurer de l’archive|Aus Archiv wiederherstellen
entity.edit|Редактировать|Edit|Editar|Editar|编辑|Modifier|Bearbeiten
entity.compose|Собрать ассет|Compose asset|Componer recurso|Montar asset|组装资产|Assembler une ressource|Asset zusammenstellen
entity.params|Параметры|Parameters|Parámetros|Parâmetros|参数|Paramètres|Parameter
entity.slots|Слоты|Slots|Ranuras|Slots|插槽|Emplacements|Slots
entity.sockets|Точки крепления|Attachment points|Puntos de anclaje|Pontos de fixação|连接点|Points de fixation|Befestigungspunkte
entity.build|Сборка|Build|Generación|Geração|构建|Génération|Build
entity.body|корпус|Body|Cuerpo|Corpo|主体|Corps|Körper
entity.structure|структура|Structure|Estructura|Estrutura|结构|Structure|Struktur
entity.part|деталь|Part|Pieza|Peça|部件|Pièce|Teil
entity.noInheritance|без наследования|No inheritance|Sin herencia|Sem herança|无继承|Sans héritage|Ohne Vererbung
entity.rating|рейтинг|Rating|Valoración|Avaliação|评分|Note|Bewertung
entity.noRating|без рейтинга|Unrated|Sin valoración|Sem avaliação|未评分|Sans note|Nicht bewertet
entity.removeRating|Снять рейтинг|Clear rating|Quitar valoración|Remover avaliação|清除评分|Effacer la note|Bewertung entfernen
entity.other|Прочее|Other|Otros|Outros|其他|Autres|Sonstiges
entity.changedHint| — подсвечены изменённые в этом варианте| — changed values are highlighted| — se resaltan los valores modificados| — valores alterados estão destacados| — 高亮显示此变体的更改值| — les valeurs modifiées sont surlignées| — geänderte Werte sind hervorgehoben
entity.onlyDifferences| только различия| Differences only| Solo diferencias| Apenas diferenças| 仅显示差异| Différences uniquement| Nur Unterschiede
entity.parameter|параметр|Parameter|Parámetro|Parâmetro|参数|Paramètre|Parameter
branch.parentValue|значение в родителе|Parent value|Valor del padre|Valor do pai|父变体的值|Valeur du parent|Wert des Vorgängers
branch.note|что меняем и зачем|What changes and why|Qué cambia y por qué|O que muda e por quê|更改内容及原因|Ce qui change et pourquoi|Was sich ändert und warum
branch.newNote|заметка для новой ветки|Note for the new branch|Nota para la nueva rama|Nota para a nova ramificação|新分支的备注|Note pour la nouvelle branche|Notiz zur neuen Verzweigung
branch.save|Сохранить как ветку|Save as branch|Guardar como rama|Salvar como ramificação|保存为分支|Enregistrer comme branche|Als Verzweigung speichern
branch.changed|изменено параметров: {count}|Changed parameters: {count}|Parámetros modificados: {count}|Parâmetros alterados: {count}|已更改参数：{count}|Paramètres modifiés : {count}|Geänderte Parameter: {count}
compose.params|Параметры сборки|Assembly parameters|Parámetros de ensamblaje|Parâmetros de montagem|组装参数|Paramètres d’assemblage|Zusammenbauparameter
compose.select|— выберите —|— select —|— seleccionar —|— selecionar —|— 请选择 —|— sélectionner —|— auswählen —
compose.empty|— пусто —|— empty —|— vacío —|— vazio —|— 空 —|— vide —|— leer —
compose.body|корпус (body)|Body (body)|Cuerpo (body)|Corpo (body)|主体（body）|Corps (body)|Körper (body)
compose.newRoot|(новый корень)|(new root)|(nueva raíz)|(nova raiz)|（新根节点）|(nouvelle racine)|(neuer Ursprung)
compose.parent|родитель|Parent|Padre|Pai|父变体|Parent|Vorgänger
compose.note|что собираем|What to assemble|Qué ensamblar|O que montar|组装目标|Ce qu’on assemble|Was zusammengebaut wird
compose.noCompatible|Нет собранных совместимых вариантов — соберите компонент или ассет.|No compatible built variants. Build a component or asset first.|No hay variantes generadas compatibles. Genera primero un componente o recurso.|Não há variantes geradas compatíveis. Gere um componente ou asset primeiro.|无兼容的已构建变体。请先构建组件或资产。|Aucune variante générée compatible. Générez d’abord un composant ou une ressource.|Keine kompatiblen erstellten Varianten. Zuerst eine Komponente oder ein Asset erstellen.
compose.help|Для каждого слота — готовые варианты компонентов и ассетов, совместимые по интерфейсу слота.|Each slot lists built components and assets compatible with its interface.|Cada ranura muestra componentes y recursos generados compatibles con su interfaz.|Cada slot lista componentes e assets gerados compatíveis com sua interface.|每个插槽列出与其接口兼容的已构建组件和资产。|Chaque emplacement propose des composants et ressources générés compatibles.|Jeder Slot zeigt erstellte Komponenten und Assets mit kompatibler Schnittstelle.
compose.deltaHelp|В вариант сохраняются только слоты и параметры, отличающиеся от родителя.|Only slots and parameters differing from the parent are saved.|Solo se guardan ranuras y parámetros diferentes del padre.|Apenas slots e parâmetros diferentes do pai são salvos.|仅保存与父变体不同的插槽和参数。|Seuls les emplacements et paramètres différents du parent sont enregistrés.|Nur vom Vorgänger abweichende Slots und Parameter werden gespeichert.
create.title|Новый ассет|New asset|Nuevo recurso|Novo asset|新建资产|Nouvelle ressource|Neues Asset
create.assetName|Название ассета|Asset name|Nombre del recurso|Nome do asset|资产名称|Nom de la ressource|Asset-Name
create.description|Что делает этот ассет|What this asset does|Qué hace este recurso|O que este asset faz|此资产的用途|Fonction de cette ressource|Funktion dieses Assets
create.firstVariant|Первый вариант|First variant|Primera variante|Primeira variante|首个变体|Première variante|Erste Variante
create.chooseVariant|— выберите готовый вариант —|— select a built variant —|— elige una variante generada —|— selecione uma variante gerada —|— 选择已构建变体 —|— choisir une variante générée —|— erstellte Variante wählen —
create.base|Основа / body|Base / body|Base / body|Base / body|基础／body|Base / body|Basis / body
create.removeSlot|Удалить слот|Remove slot|Quitar ranura|Remover slot|删除插槽|Retirer l’emplacement|Slot entfernen
create.readyModel|Готовая модель|Built model|Modelo generado|Modelo gerado|已构建模型|Modèle généré|Erstelltes Modell
create.slotName|Имя слота|Slot name|Nombre de ranura|Nome do slot|插槽名称|Nom d’emplacement|Slot-Name
create.attachment|Крепление|Attachment|Anclaje|Fixação|连接位置|Fixation|Befestigung
create.chooseSocket|— выберите сокет —|— select a socket —|— elige un punto de anclaje —|— selecione um socket —|— 选择连接点 —|— choisir un socket —|— Socket auswählen —
create.offset|Смещение от сокета, м|Offset from socket, m|Desplazamiento del anclaje, m|Deslocamento do socket, m|相对连接点的偏移（米）|Décalage du socket, m|Versatz vom Socket, m
create.origin|Корпус задаёт начало координат нового ассета.|The body sets the origin of the new asset.|El cuerpo define el origen del nuevo recurso.|O corpo define a origem do novo asset.|主体定义新资产的坐标原点。|Le corps définit l’origine de la nouvelle ressource.|Der Körper legt den Ursprung des neuen Assets fest.
create.noSocket|У предыдущих частей нет совместимых свободных сокетов для этой детали.|Earlier parts have no free compatible socket for this part.|Las piezas anteriores no tienen anclajes libres compatibles con esta pieza.|As peças anteriores não têm sockets livres compatíveis com esta peça.|之前的部件没有与此部件兼容的空闲连接点。|Les pièces précédentes n’ont aucun socket libre compatible.|Vorherige Teile haben keinen freien kompatiblen Socket für dieses Teil.
create.invalidId|ID: латинские строчные буквы, цифры и _; начинается с буквы.|ID: lowercase Latin letters, digits and _; start with a letter.|ID: letras latinas minúsculas, dígitos y _; empieza con letra.|ID: letras latinas minúsculas, dígitos e _; comece com uma letra.|ID：小写拉丁字母、数字及 _；以字母开头。|ID : lettres latines minuscules, chiffres et _ ; commencer par une lettre.|ID: kleine lateinische Buchstaben, Ziffern und _; mit Buchstaben beginnen.
create.needName|Укажите название ассета.|Enter an asset name.|Introduce un nombre para el recurso.|Insira um nome para o asset.|请输入资产名称。|Saisissez un nom de ressource.|Asset-Namen eingeben.
create.needBody|Выберите основу для слота body.|Select a base for the body slot.|Elige una base para la ranura body.|Selecione uma base para o slot body.|请选择 body 插槽的基础模型。|Choisissez une base pour l’emplacement body.|Basis für den Slot body auswählen.
create.gridError|Габаритная сетка: целые значения от 1 до 256.|Bounding grid: integers from 1 to 256.|Cuadrícula de límites: enteros de 1 a 256.|Grade de limites: inteiros de 1 a 256.|边界网格：1 到 256 的整数。|Grille de limites : entiers de 1 à 256.|Begrenzungsraster: ganze Zahlen von 1 bis 256.
create.composition|Композиция|Composition|Composición|Composição|组合|Composition|Zusammenstellung
create.addPart|+ Добавить компонент или ассет|+ Add component or asset|+ Añadir componente o recurso|+ Adicionar componente ou asset|+ 添加组件或资产|+ Ajouter un composant ou une ressource|+ Komponente oder Asset hinzufügen
create.bounds|Описание и габариты|Description and bounds|Descripción y dimensiones|Descrição e dimensões|说明与尺寸|Description et dimensions|Beschreibung und Abmessungen
create.grid|Габаритная сетка, vox|Bounding grid, vox|Cuadrícula de límites, vox|Grade de limites, vox|边界网格（vox）|Grille de limites, vox|Begrenzungsraster, vox
create.tags|Теги первого варианта|First variant tags|Etiquetas de la primera variante|Tags da primeira variante|首个变体的标签|Étiquettes de la première variante|Tags der ersten Variante
create.variantNote|Примечание к варианту|Variant note|Nota de la variante|Nota da variante|变体备注|Note de variante|Variantennotiz
viewer.iso|Изометрия|Isometric|Isométrica|Isométrica|等轴测|Isométrique|Isometrisch
viewer.front|Спереди|Front|Frontal|Frente|前视|Face|Vorne
viewer.back|Сзади|Back|Trasera|Trás|后视|Dos|Hinten
viewer.right|Справа|Right|Derecha|Direita|右视|Droite|Rechts
viewer.left|Слева|Left|Izquierda|Esquerda|左视|Gauche|Links
viewer.top|Сверху|Top|Superior|Superior|顶视|Dessus|Oben
viewer.bottom|Снизу|Bottom|Inferior|Inferior|底视|Dessous|Unten
viewer.side|Сбоку|Side|Lateral|Lateral|侧视|Côté|Seite
viewer.pose|Поза|Pose|Pose|Pose|姿势|Pose|Pose
viewer.autoRotate|Автовращение|Auto rotate|Rotación automática|Rotação automática|自动旋转|Rotation automatique|Automatisch drehen
viewer.wireframe|Каркас|Wireframe|Malla de alambre|Aramado|线框|Fil de fer|Drahtgitter
viewer.bounds|Габарит|Bounds|Límites|Limites|边界|Limites|Abmessungen
viewer.sockets|Сокеты|Sockets|Anclajes|Sockets|连接点|Sockets|Sockets
viewer.collision|Коллизия|Collision|Colisión|Colisão|碰撞|Collision|Kollision
viewer.skeleton|Скелет|Skeleton|Esqueleto|Esqueleto|骨架|Squelette|Skelett
viewer.reset|Сбросить камеру|Reset camera|Restablecer cámara|Redefinir câmera|重置相机|Réinitialiser la caméra|Kamera zurücksetzen
viewer.replay|Повторить анимацию|Replay animation|Repetir animación|Repetir animação|重播动画|Rejouer l’animation|Animation wiederholen
viewer.pause|Приостановить анимацию|Pause animation|Pausar animación|Pausar animação|暂停动画|Suspendre l’animation|Animation pausieren
viewer.play|Продолжить анимацию|Resume animation|Continuar animación|Continuar animação|继续动画|Reprendre l’animation|Animation fortsetzen
viewer.clip|Клип анимации|Animation clip|Clip de animación|Clipe de animação|动画片段|Clip d’animation|Animationsclip
viewer.animation|анимация|Animation|Animación|Animação|动画|Animation|Animation
viewer.aim|Ручное наведение|Manual aiming|Apuntado manual|Mira manual|手动瞄准|Visée manuelle|Manuelles Zielen
viewer.yaw|Горизонтальное наведение|Horizontal aiming|Apuntado horizontal|Mira horizontal|水平瞄准|Visée horizontale|Horizontales Zielen
viewer.pitch|Вертикальное наведение|Vertical aiming|Apuntado vertical|Mira vertical|垂直瞄准|Visée verticale|Vertikales Zielen
viewer.rotation|Поворот|Rotation|Rotación|Rotação|旋转|Rotation|Drehung
viewer.elevation|Подъём|Elevation|Elevación|Elevação|仰角|Élévation|Anhebung
viewer.aimHelp|Ползунок приостанавливает демонстрацию.|The slider pauses the demonstration.|El control deslizante pausa la demostración.|O controle deslizante pausa a demonstração.|滑块会暂停演示。|Le curseur suspend la démonstration.|Der Regler pausiert die Demonstration.
viewer.synced|камеры синхронизированы|Cameras synchronized|Cámaras sincronizadas|Câmeras sincronizadas|相机已同步|Caméras synchronisées|Kameras synchronisiert
material.bands|Ступени света|Light bands|Bandas de luz|Faixas de luz|明暗色阶|Paliers de lumière|Lichtstufen
material.light|Тень и свет|Shadow and light|Sombra y luz|Sombra e luz|阴影与光照|Ombre et lumière|Schatten und Licht
material.specular|Блик|Specular highlight|Brillo especular|Brilho especular|高光|Reflet spéculaire|Glanzlicht
material.rim|Контровой свет|Rim light|Luz de contorno|Luz de contorno|轮廓光|Lumière de contour|Kantenlicht
material.halftone|Растр (комикс)|Halftone (comic)|Semitono (cómic)|Retícula (quadrinhos)|半色调（漫画）|Trame (BD)|Halbton (Comic)
material.outline|Контур|Outline|Contorno|Contorno|轮廓|Contour|Kontur
material.description|Описание материала|Material description|Descripción del material|Descrição do material|材质说明|Description du matériau|Materialbeschreibung
material.presets|Пресеты|Presets|Preajustes|Predefinições|预设|Préréglages|Voreinstellungen
material.compareHint|Shift+клик — сравнить|Shift+click to compare|Mayús+clic para comparar|Shift+clique para comparar|Shift+单击以比较|Maj+clic pour comparer|Umschalt+Klick zum Vergleichen
material.loading|Загрузка пресета…|Loading preset…|Cargando preajuste…|Carregando predefinição…|正在加载预设…|Chargement du préréglage…|Voreinstellung wird geladen…
material.error|Не удалось загрузить пресет.|Could not load the preset.|No se pudo cargar el preajuste.|Não foi possível carregar a predefinição.|无法加载预设。|Impossible de charger le préréglage.|Voreinstellung konnte nicht geladen werden.
material.model|модель|Model|Modelo|Modelo|模型|Modèle|Modell
material.pbr|PBR (как в GLB)|PBR (from GLB)|PBR (del GLB)|PBR (do GLB)|PBR（来自 GLB）|PBR (du GLB)|PBR (aus GLB)
material.compare|A/B с PBR|A/B with PBR|A/B con PBR|A/B com PBR|与 PBR 进行 A/B 比较|A/B avec PBR|A/B mit PBR
material.closeCompare|Закрыть сравнение (Esc)|Close comparison (Esc)|Cerrar comparación (Esc)|Fechar comparação (Esc)|关闭比较（Esc）|Fermer la comparaison (Échap)|Vergleich schließen (Esc)
material.renderQueued|Рендер в очереди…|Render queued…|Renderizado en cola…|Renderização na fila…|渲染已排队…|Rendu en attente…|Rendering in Warteschlange…
material.notBuilt|Не собран — «Пересобрать».|Not built — select “Rebuild”.|No generado: selecciona «Volver a generar».|Não gerado: selecione “Gerar novamente”.|尚未构建，请选择“重新构建”。|Non généré : choisissez « Regénérer ».|Noch nicht erstellt: „Neu erstellen“ wählen.
material.blenderPreview|Blender-превью|Blender preview|Vista previa en Blender|Prévia no Blender|Blender 预览|Aperçu Blender|Blender-Vorschau
projections.title|Проекции|Projections|Proyecciones|Projeções|投影|Projections|Projektionen
projections.create|Создать проекции|Create projections|Crear proyecciones|Criar projeções|创建投影|Créer des projections|Projektionen erstellen
projections.section|Проекции и снимки|Projections and snapshots|Proyecciones e imágenes|Projeções e imagens|投影与截图|Projections et captures|Projektionen und Aufnahmen
projections.loading|Снимки создаются…|Creating snapshots…|Creando imágenes…|Criando imagens…|正在创建截图…|Création des captures…|Aufnahmen werden erstellt…
projections.help|Шесть ортографических ракурсов в одном масштабе. Нажмите снимок, чтобы открыть PNG.|Six orthographic views at one scale. Click a snapshot to open the PNG.|Seis vistas ortográficas a la misma escala. Haz clic para abrir el PNG.|Seis vistas ortográficas na mesma escala. Clique para abrir o PNG.|六个相同缩放的正交视图。点击截图打开 PNG。|Six vues orthographiques à la même échelle. Cliquez pour ouvrir le PNG.|Sechs orthografische Ansichten im gleichen Maßstab. Klicken öffnet das PNG.
blockout.title|Лист блокаута|Blockout sheet|Hoja de bloques|Folha de blocagem|块状草模图板|Planche de blockout|Blockout-Übersicht
blockout.parts|Детали|Parts|Piezas|Peças|部件|Pièces|Teile
blockout.loading|Загрузка листа…|Loading sheet…|Cargando hoja…|Carregando folha…|正在加载图板…|Chargement de la planche…|Übersicht wird geladen…
blockout.openBlender|Открыть в Blender|Open in Blender|Abrir en Blender|Abrir no Blender|在 Blender 中打开|Ouvrir dans Blender|In Blender öffnen
blockout.download|Скачать .blend|Download .blend|Descargar .blend|Baixar .blend|下载 .blend|Télécharger .blend|.blend herunterladen
blockout.preparing|Подготовка листа…|Preparing sheet…|Preparando hoja…|Preparando folha…|正在准备图板…|Préparation de la planche…|Übersicht wird vorbereitet…
edit.save|Сохранить как новый вариант|Save as new variant|Guardar como nueva variante|Salvar como nova variante|保存为新变体|Enregistrer comme nouvelle variante|Als neue Variante speichern
edit.revert|Отменить все сдвиги|Revert all offsets|Revertir desplazamientos|Reverter deslocamentos|撤销所有偏移|Annuler tous les décalages|Alle Verschiebungen zurücksetzen
edit.back|Вернуться к ассету|Back to asset|Volver al recurso|Voltar ao asset|返回资产|Retour à la ressource|Zurück zum Asset
edit.source|Исходный вариант|Source variant|Variante de origen|Variante de origem|源变体|Variante source|Ausgangsvariante
edit.position|Положение|Position|Posición|Posição|位置|Position|Position
edit.snap|Снап перемещения|Movement snap|Ajuste de movimiento|Encaixe de movimento|移动吸附|Accrochage du déplacement|Verschieberaster
edit.noSnap|Без снапа|No snapping|Sin ajuste|Sem encaixe|禁用吸附|Sans accrochage|Ohne Raster
edit.note|Заметка для нового варианта|Note for new variant|Nota para la nueva variante|Nota para a nova variante|新变体的备注|Note pour la nouvelle variante|Notiz zur neuen Variante
edit.selectSlot|Выберите слот для перемещения.|Select a slot to move.|Selecciona una ranura para mover.|Selecione um slot para mover.|请选择要移动的插槽。|Sélectionnez un emplacement à déplacer.|Slot zum Verschieben auswählen.
edit.restore|Вернуть как было|Restore original|Restaurar original|Restaurar original|恢复原始值|Rétablir l’original|Original wiederherstellen
edit.centerSocket|Центрировать на сокете|Center on socket|Centrar en el anclaje|Centralizar no socket|居中到连接点|Centrer sur le socket|Am Socket zentrieren
edit.centerBody|Центрировать корпус|Center body|Centrar cuerpo|Centralizar corpo|居中主体|Centrer le corps|Körper zentrieren
stats.polygons|полигоны|Polygons|Polígonos|Polígonos|多边形|Polygones|Polygone
stats.vertices|вершины|Vertices|Vértices|Vértices|顶点|Sommets|Scheitelpunkte
stats.boundsM|габарит, м|Bounds, m|Dimensiones, m|Dimensões, m|尺寸（米）|Dimensions, m|Abmessungen, m
stats.boundsVox|габарит, vox|Bounds, vox|Dimensiones, vox|Dimensões, vox|尺寸（vox）|Dimensions, vox|Abmessungen, vox
stats.duration|длительность|Duration|Duración|Duração|时长|Durée|Dauer
stats.log|хвост лога|Log tail|Final del registro|Final do log|日志末尾|Fin du journal|Protokollende
meta.blockout|блокаут|Blockout|Bloques iniciales|Blocagem|块状草模|Blockout|Blockout
meta.silhouette|силуэт|Silhouette|Silueta|Silhueta|轮廓|Silhouette|Silhouette
meta.details|детали|Details|Detalles|Detalhes|细节|Détails|Details
meta.complexity|Уровень сложности|Complexity level|Nivel de complejidad|Nível de complexidade|复杂度级别|Niveau de complexité|Komplexitätsstufe
meta.shader|шейдер|Shader|Shader|Shader|着色器|Shader|Shader
meta.materialShader|материал / шейдер|Material / shader|Material / shader|Material / shader|材质／着色器|Matériau / shader|Material / Shader
meta.structureHint|структура: к ней крепятся другие компоненты|Structure: accepts attached components|Estructura: admite componentes acoplados|Estrutura: recebe componentes fixados|结构：可连接其他组件|Structure : accueille d’autres composants|Struktur: andere Komponenten werden daran befestigt
meta.levelHint|уровень сложности|Complexity level|Nivel de complejidad|Nível de complexidade|复杂度级别|Niveau de complexité|Komplexitätsstufe
meta.llm|создан LLM|Created by an LLM|Creado por un LLM|Criado por um LLM|由大语言模型创建|Créé par un LLM|Von einem LLM erstellt
pack.zukTruck|Грузовик Zuk|Zuk Truck|Camión Zuk|Caminhão Zuk|Zuk 卡车|Camion Zuk|Zuk-Lkw
pack.modularTruck|Модульный грузовик|Modular Truck|Camión modular|Caminhão modular|模块化卡车|Camion modulaire|Modularer Lkw
pack.truckEvolution|Эволюция грузовика|Truck Evolution|Evolución del camión|Evolução do caminhão|卡车演进|Évolution du camion|Lkw-Entwicklung
pack.heliEvolution|Эволюция лёгкого вертолёта|Light Helicopter Evolution|Evolución del helicóptero ligero|Evolução do helicóptero leve|轻型直升机演进|Évolution de l’hélicoptère léger|Entwicklung des leichten Hubschraubers
pack.truck|Грузовик|Truck|Camión|Caminhão|卡车|Camion|Lkw
pack.heli|Лёгкий вертолёт|Light Helicopter|Helicóptero ligero|Helicóptero leve|轻型直升机|Hélicoptère léger|Leichter Hubschrauber
pack.td|Tower Defence|Tower Defence|Defensa de torres|Defesa de torres|塔防|Tower Defence|Tower Defence
pack.toon|Лаборатория toon-материалов|Toon Material Lab|Laboratorio de materiales toon|Laboratório de materiais toon|卡通材质实验室|Laboratoire de matériaux toon|Toon-Materiallabor
pack.gatling|Башня Гатлинга|Gatling Tower|Torre Gatling|Torre Gatling|加特林炮塔|Tourelle Gatling|Gatling-Turm
pack.missile|Ракетная башня|Missile Tower|Torre de misiles|Torre de mísseis|导弹塔|Tourelle lance-missiles|Raketenturm
pack.support|Башня поддержки|Support Tower|Torre de apoyo|Torre de apoio|支援塔|Tourelle de soutien|Unterstützungsturm
pack.scout|Разведчик|Scout|Explorador|Batedor|侦察兵|Éclaireur|Späher
pack.grunt|Пехотинец|Grunt|Soldado|Soldado|步兵|Soldat|Soldat
pack.flyer|Летающий юнит|Flyer|Unidad aérea|Unidade aérea|飞行单位|Unité volante|Flugeinheit
pack.cover|Укрытие|Cover|Cobertura|Cobertura|掩体|Abri|Deckung
pack.path|Плитка пути|Path Tile|Baldosa de camino|Bloco de caminho|路径地块|Tuile de chemin|Wegkachel
param.stage|Стадия|Stage|Etapa|Etapa|阶段|Étape|Stufe
param.part|Часть модели|Model part|Parte del modelo|Parte do modelo|模型部件|Partie du modèle|Modellteil
param.bodyColor|Цвет корпуса|Body color|Color del cuerpo|Cor do corpo|主体颜色|Couleur du corps|Körperfarbe
param.trimColor|Цвет отделки|Trim color|Color del acabado|Cor do acabamento|装饰颜色|Couleur des finitions|Zierfarbe
param.color|Цвет|Color|Color|Cor|颜色|Couleur|Farbe
param.height|Высота|Height|Altura|Altura|高度|Hauteur|Höhe
param.width|Ширина|Width|Anchura|Largura|宽度|Largeur|Breite
param.length|Длина|Length|Longitud|Comprimento|长度|Longueur|Länge
param.depth|Глубина|Depth|Profundidad|Profundidade|深度|Profondeur|Tiefe
param.finish|Отделка материала|Material finish|Acabado del material|Acabamento do material|材质表面效果|Finition du matériau|Materialoberfläche
param.roughness|Шероховатость|Roughness|Rugosidad|Rugosidade|粗糙度|Rugosité|Rauheit
param.metallic|Металличность|Metallic|Metálico|Metálico|金属度|Métallique|Metallisch
param.bands|Число ступеней|Light band count|Número de bandas|Número de faixas|明暗色阶数|Nombre de paliers|Anzahl der Lichtstufen
param.softness|Мягкость света|Light softness|Suavidad de la luz|Suavidade da luz|光照柔和度|Douceur de lumière|Weichheit des Lichts
param.shadowStrength|Сила тени|Shadow strength|Intensidad de sombra|Intensidade da sombra|阴影强度|Intensité de l’ombre|Schattenstärke
param.shadowColor|Цвет тени|Shadow color|Color de sombra|Cor da sombra|阴影颜色|Couleur de l’ombre|Schattenfarbe
param.lightTint|Оттенок света|Light tint|Tinte de luz|Tonalidade da luz|光照色调|Teinte de lumière|Lichtfarbe
param.outlineMode|Режим контура|Outline mode|Modo de contorno|Modo de contorno|轮廓模式|Mode de contour|Konturmodus
param.outlineWidth|Ширина контура|Outline width|Grosor del contorno|Largura do contorno|轮廓宽度|Largeur du contour|Konturbreite
param.outlineColor|Цвет контура|Outline color|Color del contorno|Cor do contorno|轮廓颜色|Couleur du contour|Konturfarbe
param.specularSize|Размер блика|Highlight size|Tamaño del brillo|Tamanho do brilho|高光大小|Taille du reflet|Glanzlichtgröße
param.rimWidth|Ширина контрового света|Rim width|Anchura del contorno luminoso|Largura da luz de contorno|轮廓光宽度|Largeur du contour lumineux|Kantenlichtbreite
param.rimColor|Цвет контрового света|Rim color|Color de luz de contorno|Cor da luz de contorno|轮廓光颜色|Couleur du contour lumineux|Kantenlichtfarbe
param.halftoneScale|Масштаб растра|Halftone scale|Escala del semitono|Escala da retícula|半色调比例|Échelle de trame|Halbtonmaßstab
material.liveHelp|Слайдеры меняют шейдер вживую; «Сохранить как ветку» пишет дельту в реестр. |Sliders update the shader live; “Save as branch” writes a delta to the registry. |Los controles actualizan el shader; «Guardar como rama» escribe una delta en el registro. |Os controles atualizam o shader; “Salvar como ramificação” grava uma delta no registro. |滑块实时更新着色器；“保存为分支”将差异写入注册表。|Les curseurs modifient le shader en direct ; « Enregistrer comme branche » écrit un delta. |Regler ändern den Shader live; „Als Verzweigung speichern“ schreibt ein Delta in die Registry. 
material.previewHelp|Превью в дереве — Blender-реализация, вьюер — three.js, для игры — Godot-файлы справа.|Tree previews use Blender, the viewer uses three.js; game files for Godot are on the right.|Las vistas del árbol usan Blender y el visor three.js; los archivos Godot están a la derecha.|As prévias da árvore usam Blender, o visualizador usa three.js; arquivos Godot estão à direita.|树状预览使用 Blender，查看器使用 three.js；Godot 游戏文件在右侧。|L’arbre utilise Blender, le visualiseur three.js ; les fichiers Godot sont à droite.|Baumvorschauen verwenden Blender, der Viewer three.js; Godot-Dateien stehen rechts.
material.pbrHint|рядом та же модель в исходном PBR|Same model alongside with its original PBR material|El mismo modelo al lado con su material PBR original|O mesmo modelo ao lado com o material PBR original|旁边显示同一模型的原始 PBR 材质|Même modèle à côté avec son matériau PBR d’origine|Dasselbe Modell daneben mit ursprünglichem PBR-Material
material.exportHelp|Шейдеры положить в res://shaders/, .tres — материал с параметрами этого пресета (hull-контур — next_pass).|Place shaders in res://shaders/. The .tres contains this preset; hull outlines use next_pass.|Pon los shaders en res://shaders/. El .tres contiene este preajuste; el contorno hull usa next_pass.|Coloque shaders em res://shaders/. O .tres contém esta predefinição; contornos hull usam next_pass.|将着色器放入 res://shaders/。.tres 包含此预设；外壳轮廓使用 next_pass。|Placez les shaders dans res://shaders/. Le .tres contient ce préréglage ; le contour hull utilise next_pass.|Shader in res://shaders/ ablegen. Die .tres enthält diese Voreinstellung; Hull-Konturen verwenden next_pass.
viewer.materialHint|Материал: PBR из GLB или toon-пресет из реестра|Material: GLB PBR or a registry toon preset|Material: PBR del GLB o preajuste toon del registro|Material: PBR do GLB ou predefinição toon do registro|材质：GLB 的 PBR 或注册表中的卡通预设|Matériau : PBR du GLB ou préréglage toon du registre|Material: PBR aus GLB oder Toon-Voreinstellung der Registry
viewer.gridHint|Воксельная сетка габарита (interface.grid_size)|Voxel bounding grid (interface.grid_size)|Cuadrícula de límites voxel (interface.grid_size)|Grade de limites voxel (interface.grid_size)|体素边界网格（interface.grid_size）|Grille voxel des limites (interface.grid_size)|Voxel-Begrenzungsraster (interface.grid_size)
viewer.showSockets|Показать сокеты|Show sockets|Mostrar anclajes|Mostrar sockets|显示连接点|Afficher les sockets|Sockets anzeigen
viewer.showCollision|Показать -colonly меш|Show -colonly mesh|Mostrar malla -colonly|Mostrar malha -colonly|显示 -colonly 网格|Afficher le maillage -colonly|-colonly-Mesh anzeigen
viewer.showBones|Показать кости (персонажи)|Show bones (characters)|Mostrar huesos (personajes)|Mostrar ossos (personagens)|显示骨骼（角色）|Afficher les os (personnages)|Knochen anzeigen (Charaktere)
viewer.webglLost|Видеокарта сбросила WebGL — восстанавливаю…|WebGL context lost — restoring…|Contexto WebGL perdido; restaurando…|Contexto WebGL perdido; restaurando…|WebGL 上下文丢失，正在恢复…|Contexte WebGL perdu : restauration…|WebGL-Kontext verloren — wird wiederhergestellt…
viewer.noParts|Нет собранных деталей на столе|No built parts on the table|No hay piezas generadas en la mesa|Não há peças geradas na mesa|桌面没有已构建的部件|Aucune pièce générée sur la table|Keine erstellten Teile auf dem Tisch
create.help|Соберите корпус и детали из готовых вариантов компонентов или ассетов. Каждый дочерний слот крепится к сокету уже добавленной части.|Assemble the body and parts from built variants. Each child slot attaches to a socket of an earlier part.|Ensambla cuerpo y piezas con variantes generadas. Cada ranura hija se fija a un anclaje de una pieza anterior.|Monte corpo e peças com variantes geradas. Cada slot filho se conecta ao socket de uma peça anterior.|使用已构建的变体组装主体和部件。每个子插槽连接到先前部件的连接点。|Assemblez le corps et les pièces à partir de variantes générées. Chaque enfant se fixe à un socket d’une pièce précédente.|Körper und Teile aus erstellten Varianten zusammenbauen. Jeder untergeordnete Slot wird an einem Socket eines vorherigen Teils befestigt.
create.voxelHelp|1 vox = 0,25 м. Свободные сокеты корпуса будут доступны снаружи нового ассета.|1 vox = 0.25 m. Free body sockets remain accessible on the new asset.|1 vox = 0,25 m. Los anclajes libres del cuerpo quedan disponibles en el nuevo recurso.|1 vox = 0,25 m. Sockets livres do corpo ficam disponíveis no novo asset.|1 vox = 0.25 米。主体的空闲连接点仍可在新资产外部使用。|1 vox = 0,25 m. Les sockets libres du corps restent accessibles sur la nouvelle ressource.|1 vox = 0,25 m. Freie Körper-Sockets bleiben am neuen Asset zugänglich.
entity.docResolved|Резолвленное описание (наследование применено)|Resolved description (inheritance applied)|Descripción resuelta (herencia aplicada)|Descrição resolvida (herança aplicada)|解析后的说明（已应用继承）|Description résolue (héritage appliqué)|Aufgelöste Beschreibung (Vererbung angewandt)
entity.llmContext|это же уйдёт в контекст LLM|This is also sent to the LLM context|Esto también se envía al contexto del LLM|Isto também é enviado ao contexto do LLM|同样会发送到大语言模型的上下文|Également envoyé au contexte du LLM|Wird auch an den LLM-Kontext gesendet
entity.diffUnavailable|Дифф недоступен (один из вариантов невалиден).|Comparison unavailable: one variant is invalid.|Comparación no disponible: una variante no es válida.|Comparação indisponível: uma variante é inválida.|无法比较：一个变体无效。|Comparaison indisponible : une variante est invalide.|Vergleich nicht verfügbar: eine Variante ist ungültig.
entity.sameArtifact| — одинаковые, один артефакт| — identical, same artifact| — idénticos, mismo artefacto| — idênticos, mesmo artefato| — 相同，使用同一产物| — identiques, même artefact| — identisch, dasselbe Artefakt
entity.root| · корень| · root| · raíz| · raiz| · 根节点| · racine| · Ursprung
entity.forkBlender|Ветка в Blender|Branch in Blender|Crear rama en Blender|Criar ramificação no Blender|在 Blender 中创建分支|Créer une branche dans Blender|In Blender verzweigen
entity.openedBlender|Открыт в Blender|Open in Blender|Abierto en Blender|Aberto no Blender|已在 Blender 中打开|Ouvert dans Blender|In Blender geöffnet
entity.blenderAlready|Окно Blender с этим файлом уже открыто|This file is already open in Blender|Este archivo ya está abierto en Blender|Este arquivo já está aberto no Blender|此文件已在 Blender 中打开|Ce fichier est déjà ouvert dans Blender|Diese Datei ist bereits in Blender geöffnet
entity.manualSlots|Слоты и смещения ниже на модель не влияют. |The slots and offsets below do not affect this model. |Las ranuras y desplazamientos siguientes no afectan al modelo. |Os slots e deslocamentos abaixo não afetam este modelo. |下方的插槽和偏移不影响此模型。|Les emplacements et décalages ci-dessous ne modifient pas ce modèle. |Die folgenden Slots und Versätze beeinflussen dieses Modell nicht. 
entity.manualParams|Параметры ниже на модель не влияют. |The parameters below do not affect this model. |Los parámetros siguientes no afectan al modelo. |Os parâmetros abaixo não afetam este modelo. |下方的参数不影响此模型。|Les paramètres ci-dessous ne modifient pas ce modèle. |Die folgenden Parameter beeinflussen dieses Modell nicht. 
entity.blenderSaveHelp|В Blender: боковая панель (N) → вкладка Registry → «Сохранить и собрать».|In Blender: sidebar (N) → Registry tab → “Save and build”.|En Blender: panel lateral (N) → pestaña Registry → «Save and build».|No Blender: painel lateral (N) → aba Registry → “Save and build”.|在 Blender 中：侧边栏（N）→ Registry 标签 →“Save and build”。|Dans Blender : panneau latéral (N) → Registry → « Save and build ».|In Blender: Seitenleiste (N) → Registry → „Save and build“.
entity.freeSockets| — свободные останутся в GLB как socket_*| — free sockets remain in GLB as socket_*| — los libres quedan en GLB como socket_*| — sockets livres ficam no GLB como socket_*| — 空闲连接点在 GLB 中保留为 socket_*| — les sockets libres restent dans le GLB sous socket_*| — freie Sockets bleiben als socket_* in der GLB
entity.socketInterface| — интерфейс для слотов ассетов| — interface for asset slots| — interfaz para ranuras de recursos| — interface para slots de assets| — 资产插槽的接口| — interface des emplacements d’assets| — Schnittstelle für Asset-Slots
entity.socketOccupied|занята слотом|Occupied by a slot|Ocupado por una ranura|Ocupado por um slot|已被插槽占用|Occupé par un emplacement|Von einem Slot belegt
entity.verified|проверена|Verified|Verificado|Verificado|已验证|Vérifié|Geprüft
entity.compositionVerified|Композиция · проверена|Composition · verified|Composición · verificada|Composição · verificada|组合 · 已验证|Composition · vérifiée|Zusammenstellung · geprüft
edit.help|Выберите деталь в списке или нажмите на неё в модели. Оси glTF: X — вправо, Y — вверх, Z — к фасаду.|Select a part in the list or click the model. glTF axes: X right, Y up, Z forward.|Selecciona una pieza en la lista o modelo. Ejes glTF: X derecha, Y arriba, Z al frente.|Selecione uma peça na lista ou modelo. Eixos glTF: X direita, Y cima, Z frente.|从列表或模型中选择部件。glTF 轴：X 向右，Y 向上，Z 向前。|Choisissez une pièce dans la liste ou le modèle. Axes glTF : X droite, Y haut, Z avant.|Teil in Liste oder Modell wählen. glTF-Achsen: X rechts, Y oben, Z nach vorne.
edit.dragHelp|Перетаскивайте цветные оси гизмо или задавайте координаты ниже.|Drag the colored gizmo axes or enter coordinates below.|Arrastra los ejes de colores o introduce coordenadas abajo.|Arraste os eixos coloridos ou insira coordenadas abaixo.|拖动彩色操作轴，或在下方输入坐标。|Déplacez les axes colorés ou saisissez les coordonnées ci-dessous.|Farbige Gizmo-Achsen ziehen oder unten Koordinaten eingeben.
edit.offsetHelp|Смещение относительно сокета, метры. Положительное Z — вперёд к фасаду.|Offset from the socket in meters. Positive Z points forward.|Desplazamiento del anclaje en metros. Z positivo apunta al frente.|Deslocamento do socket em metros. Z positivo aponta para a frente.|相对连接点的偏移，以米为单位。Z 正方向朝前。|Décalage du socket en mètres. Z positif pointe vers l’avant.|Versatz vom Socket in Metern. Positives Z zeigt nach vorne.
edit.noneOccupied|В этом варианте нет занятых слотов.|This variant has no occupied slots.|Esta variante no tiene ranuras ocupadas.|Esta variante não tem slots ocupados.|此变体没有已占用的插槽。|Cette variante n’a aucun emplacement occupé.|Diese Variante hat keine belegten Slots.
edit.originalUnbuilt|Исходный вариант ещё не собран. Соберите его для предпросмотра.|The source variant is not built. Build it to enable preview.|La variante de origen no está generada. Genérala para activar la vista previa.|A variante de origem não foi gerada. Gere-a para ativar a prévia.|源变体尚未构建。请构建后查看预览。|La variante source n’est pas générée. Générez-la pour l’aperçu.|Ausgangsvariante noch nicht erstellt. Für eine Vorschau erstellen.
edit.missingNodes|Некоторые слоты не найдены в GLB; их можно изменить численно.|Some slots are missing from the GLB; edit their coordinates numerically.|Faltan ranuras en el GLB; edita sus coordenadas numéricamente.|Alguns slots não estão no GLB; edite suas coordenadas numericamente.|GLB 中缺少部分插槽；可通过数值修改坐标。|Des emplacements manquent dans le GLB ; modifiez leurs coordonnées.|Einige Slots fehlen in der GLB; Koordinaten können numerisch bearbeitet werden.
edit.choosePart|Выбрать деталь в модели|Select part in model|Seleccionar pieza en modelo|Selecionar peça no modelo|在模型中选择部件|Sélectionner la pièce dans le modèle|Teil im Modell auswählen
edit.noNode|Нет отдельного узла в текущем GLB|No separate node in the current GLB|Sin nodo separado en el GLB actual|Sem nó separado no GLB atual|当前 GLB 中没有独立节点|Aucun nœud séparé dans le GLB actuel|Kein eigener Knoten in der aktuellen GLB
edit.snapHint|Шаг привязки при перемещении|Movement snap step|Paso de ajuste al mover|Passo de encaixe ao mover|移动吸附步长|Pas d’accrochage du déplacement|Rasterschritt beim Verschieben
edit.notePlaceholder|Что изменили и зачем|What changed and why|Qué cambió y por qué|O que mudou e por quê|更改内容及原因|Ce qui a changé et pourquoi|Was geändert wurde und warum
edit.leftRight|влево / вправо|Left / right|Izquierda / derecha|Esquerda / direita|左／右|Gauche / droite|Links / rechts
edit.downUp|вниз / вверх|Down / up|Abajo / arriba|Baixo / cima|下／上|Bas / haut|Unten / oben
edit.backForward|назад / вперёд|Back / forward|Atrás / adelante|Trás / frente|后／前|Arrière / avant|Zurück / vorwärts
edit.backDirection|назад|Back|Atrás|Trás|后|Arrière|Zurück
edit.forward|вперёд|Forward|Adelante|Frente|前|Avant|Vorwärts
edit.center|центр ассета|Asset center|Centro del recurso|Centro do asset|资产中心|Centre de la ressource|Asset-Mitte
core.asset|Ассет|Asset|Recurso|Asset|资产|Ressource|Asset
core.component|Компонент|Component|Componente|Componente|组件|Composant|Komponente
core.tagVariant|Тег варианта|Variant tag|Etiqueta de variante|Tag de variante|变体标签|Étiquette de variante|Varianten-Tag
core.noTags|без тегов|No tags|Sin etiquetas|Sem tags|无标签|Sans étiquettes|Ohne Tags
core.unavailablePreview|Превью недоступно|Preview unavailable|Vista previa no disponible|Prévia indisponível|预览不可用|Aperçu indisponible|Vorschau nicht verfügbar
core.cast|Каст|Cast|Reparto|Elenco|角色阵容|Distribution|Besetzung
core.castTogether|Каст: все вместе|Cast: all together|Reparto: todos juntos|Elenco: todos juntos|阵容：全部角色|Distribution : ensemble|Besetzung: alle zusammen
core.animations|Набор анимаций|Animation set|Conjunto de animaciones|Conjunto de animações|动画集|Ensemble d’animations|Animationssatz
core.clipMissing|нет в сборке|Missing from build|Falta en la generación|Ausente da geração|构建中缺失|Absent de la génération|Fehlt im Build
core.sharedSkeleton|общий скелет|Shared skeleton|Esqueleto compartido|Esqueleto compartilhado|共享骨架|Squelette partagé|Gemeinsames Skelett
core.rig|риг|Rig|Rig|Rig|绑定骨架|Rig|Rig
core.noRig|без рига|No rig|Sin rig|Sem rig|无绑定骨架|Sans rig|Ohne Rig
core.modified| (изменён)| (modified)| (modificado)| (alterado)|（已修改）| (modifié)| (geändert)
core.modifiedDot| · изменён| · modified| · modificado| · alterado| · 已修改| · modifié| · geändert
core.newBreadcrumb| / новый| / new| / nuevo| / novo| / 新建| / nouveau| / neu
core.composeBreadcrumb| / сборка| / assembly| / ensamblaje| / montagem| / 组装| / assemblage| / Zusammenbau
core.editBreadcrumb| / редактирование| / edit| / editar| / editar| / 编辑| / modification| / Bearbeitung
core.variantMany|вариантов|variants|variantes|variantes|个变体|variantes|Varianten
core.variantOne|вариант|variant|variante|variante|个变体|variante|Variante
core.variantFew|варианта|variants|variantes|variantes|个变体|variantes|Varianten
core.addTag|+ тег|+ tag|+ etiqueta|+ tag|+ 标签|+ étiquette|+ Tag
core.builtCheck|собран ✓|Built ✓|Generado ✓|Gerado ✓|已构建 ✓|Généré ✓|Erstellt ✓
core.required| · обязательный| · required| · obligatorio| · obrigatório| · 必填| · obligatoire| · erforderlich
core.optional| · необязательный| · optional| · opcional| · opcional| · 可选| · facultatif| · optional
tags.related|Связанные компоненты и ассеты|Related components and assets|Componentes y recursos relacionados|Componentes e assets relacionados|关联的组件和资产|Composants et ressources liés|Zugehörige Komponenten und Assets
tags.registry|Теги реестра|Registry tags|Etiquetas del registro|Tags do registro|注册表标签|Étiquettes du registre|Registry-Tags
tags.unavailable|Список тегов недоступен|Tag list unavailable|Lista de etiquetas no disponible|Lista de tags indisponível|标签列表不可用|Liste des étiquettes indisponible|Tag-Liste nicht verfügbar
tags.loading|Читаем теги реестра…|Loading registry tags…|Cargando etiquetas del registro…|Carregando tags do registro…|正在加载注册表标签…|Chargement des étiquettes…|Registry-Tags werden geladen…
tags.reloadHelp|Повторите загрузку списка тегов.|Reload the tag list.|Vuelve a cargar la lista de etiquetas.|Recarregue a lista de tags.|请重新加载标签列表。|Rechargez la liste des étiquettes.|Tag-Liste erneut laden.
tags.loadingCards|Загрузка тегов и карточек…|Loading tags and cards…|Cargando etiquetas y tarjetas…|Carregando tags e cartões…|正在加载标签和卡片…|Chargement des étiquettes et cartes…|Tags und Karten werden geladen…
tags.base| · база для наследования| · inheritance base| · base de herencia| · base de herança| · 继承基础| · base d’héritage| · Vererbungsbasis
tags.structure| · структура| · structure| · estructura| · estrutura| · 结构| · structure| · Struktur
tags.unavailableRetry|Список тегов недоступен. Повторите загрузку.|Tag list unavailable. Reload it.|Lista de etiquetas no disponible. Vuelve a cargarla.|Lista de tags indisponível. Recarregue.|标签列表不可用。请重新加载。|Liste indisponible. Rechargez-la.|Tag-Liste nicht verfügbar. Erneut laden.
tags.selectHelp|Выберите тег слева, чтобы увидеть связанные карточки и изменить его.|Select a tag on the left to see related cards and edit it.|Elige una etiqueta a la izquierda para ver sus tarjetas y editarla.|Selecione uma tag à esquerda para ver seus cartões e editá-la.|在左侧选择标签以查看关联卡片并编辑。|Choisissez une étiquette à gauche pour afficher ses cartes et la modifier.|Links einen Tag wählen, um zugehörige Karten anzuzeigen und ihn zu ändern.
tags.noEntityTags|В реестре пока нет тегов компонентов и ассетов.|No component or asset tags yet.|Aún no hay etiquetas de componentes o recursos.|Ainda não há tags de componentes ou assets.|暂无组件或资产标签。|Aucune étiquette de composant ou ressource.|Noch keine Komponenten- oder Asset-Tags.
tags.relatedType|Тип связанных карточек|Related card type|Tipo de tarjetas relacionadas|Tipo de cartões relacionados|关联卡片类型|Type de cartes liées|Typ der zugehörigen Karten
tags.noRelated|В этом разделе нет связанных карточек.|No related cards in this section.|No hay tarjetas relacionadas en esta sección.|Não há cartões relacionados nesta seção.|此分区没有关联卡片。|Aucune carte liée dans cette section.|Keine zugehörigen Karten in diesem Bereich.
tags.onlySettings|Тег используется только в настройках важных тегов.|This tag is used only in priority tag settings.|Esta etiqueta solo se usa en ajustes de etiquetas prioritarias.|Esta tag é usada apenas nas configurações de tags prioritárias.|此标签仅用于优先标签设置。|Cette étiquette sert uniquement aux réglages prioritaires.|Dieser Tag wird nur in den Einstellungen wichtiger Tags verwendet.
catalog.importantLabel|важные:|Priority:|Prioritarias:|Prioritárias:|优先：|Prioritaires :|Wichtig:
catalog.otherLabel|остальные:|Other:|Otras:|Outras:|其他：|Autres :|Weitere:
catalog.tagsLabel|теги:|Tags:|Etiquetas:|Tags:|标签：|Étiquettes :|Tags:
catalog.groupLabel|группа:|Group:|Grupo:|Grupo:|分组：|Groupe :|Gruppe:
catalog.levelLabel|уровень:|Level:|Nivel:|Nível:|级别：|Niveau :|Stufe:
catalog.closeSettings|Закрыть настройку|Close settings|Cerrar ajustes|Fechar configurações|关闭设置|Fermer les réglages|Einstellungen schließen
catalog.configureTags|Настроить важные теги|Configure priority tags|Configurar etiquetas prioritarias|Configurar tags prioritárias|配置优先标签|Configurer les étiquettes prioritaires|Wichtige Tags konfigurieren
catalog.tagSettingsUnavailable|Настройки тегов недоступны|Tag settings unavailable|Ajustes de etiquetas no disponibles|Configurações de tags indisponíveis|标签设置不可用|Réglages des étiquettes indisponibles|Tag-Einstellungen nicht verfügbar
catalog.closeGroups|Закрыть группы|Close groups|Cerrar grupos|Fechar grupos|关闭分组|Fermer les groupes|Gruppen schließen
catalog.groupsUnavailable|Группы недоступны|Groups unavailable|Grupos no disponibles|Grupos indisponíveis|分组不可用|Groupes indisponibles|Gruppen nicht verfügbar
catalog.tagPlaceholder|Введите тег|Enter a tag|Introduce una etiqueta|Insira uma tag|输入标签|Saisissez une étiquette|Tag eingeben
catalog.addPriority|Добавить важный тег|Add priority tag|Añadir etiqueta prioritaria|Adicionar tag prioritária|添加优先标签|Ajouter une étiquette prioritaire|Wichtigen Tag hinzufügen
catalog.tagsSaved|Важные теги сохранены|Priority tags saved|Etiquetas prioritarias guardadas|Tags prioritárias salvas|优先标签已保存|Étiquettes prioritaires enregistrées|Wichtige Tags gespeichert
catalog.settingsError|Не удалось сохранить настройки|Could not save settings|No se pudieron guardar los ajustes|Não foi possível salvar as configurações|无法保存设置|Impossible d’enregistrer les réglages|Einstellungen konnten nicht gespeichert werden
catalog.allSections|для всех разделов реестра|For all registry sections|Para todas las secciones del registro|Para todas as seções do registro|适用于全部注册表分区|Pour toutes les sections du registre|Für alle Registry-Bereiche
catalog.tagOrderHelp|Теги идут в заданном порядке и показываются отдельно, если есть в текущем разделе.|Tags follow this order and appear separately when present in the current section.|Las etiquetas siguen este orden y aparecen aparte cuando existen en la sección.|As tags seguem esta ordem e aparecem separadas quando existem na seção.|标签按此顺序排列，在当前分区存在时单独显示。|Les étiquettes suivent cet ordre et s’affichent séparément dans la section.|Tags folgen dieser Reihenfolge und erscheinen separat, wenn sie im Bereich vorkommen.
catalog.moveUp|Поднять |Move up |Subir |Mover para cima |上移 |Monter |Nach oben 
catalog.moveDown|Опустить |Move down |Bajar |Mover para baixo |下移 |Descendre |Nach unten 
catalog.emptyTagList|Список пуст. Добавьте тег ниже.|The list is empty. Add a tag below.|La lista está vacía. Añade una etiqueta abajo.|A lista está vazia. Adicione uma tag abaixo.|列表为空。请在下方添加标签。|La liste est vide. Ajoutez une étiquette ci-dessous.|Liste leer. Unten einen Tag hinzufügen.
catalog.groupId|ID новой группы|New group ID|ID del nuevo grupo|ID do novo grupo|新分组 ID|ID du nouveau groupe|ID der neuen Gruppe
catalog.groupName|Название группы|Group name|Nombre del grupo|Nome do grupo|分组名称|Nom du groupe|Gruppenname
catalog.newGroupName|Название новой группы|New group name|Nombre del nuevo grupo|Nome do novo grupo|新分组名称|Nom du nouveau groupe|Name der neuen Gruppe
catalog.invalidGroupId|ID группы: латинские строчные буквы, цифры и _, начиная с буквы.|Group ID: lowercase Latin letters, digits and _, starting with a letter.|ID del grupo: letras latinas minúsculas, dígitos y _, empezando con letra.|ID do grupo: letras latinas minúsculas, dígitos e _, começando com letra.|分组 ID：小写拉丁字母、数字及 _，以字母开头。|ID du groupe : lettres latines minuscules, chiffres et _, commençant par une lettre.|Gruppen-ID: kleine lateinische Buchstaben, Ziffern und _, mit Buchstaben beginnen.
catalog.needGroupName|Укажите название группы.|Enter a group name.|Introduce un nombre de grupo.|Insira um nome de grupo.|请输入分组名称。|Saisissez un nom de groupe.|Gruppennamen eingeben.
catalog.logicalGroups|Логические группы|Catalog groups|Grupos del catálogo|Grupos do catálogo|目录分组|Groupes du catalogue|Kataloggruppen
catalog.orderOnly|только порядок в каталоге|Catalog order only|Solo orden del catálogo|Apenas ordem do catálogo|仅影响目录顺序|Ordre du catalogue uniquement|Nur Katalogreihenfolge
catalog.groupHelp|Назначайте группы записям ниже. Это не меняет теги, сокеты, сборку и хэш моделей.|Assign entries to groups below. Tags, sockets, builds and model hashes stay unchanged.|Asigna las entradas a grupos. Las etiquetas, anclajes, generaciones y hashes no cambian.|Atribua entradas a grupos. Tags, sockets, gerações e hashes não mudam.|在下方分配条目所属分组。标签、连接点、构建及模型哈希保持不变。|Affectez les entrées aux groupes. Étiquettes, sockets, générations et hachages restent identiques.|Einträge unten Gruppen zuweisen. Tags, Sockets, Builds und Modell-Hashes bleiben unverändert.
catalog.emptyGroupName|Название группы не может быть пустым.|Group name cannot be empty.|El nombre del grupo no puede estar vacío.|O nome do grupo não pode estar vazio.|分组名称不能为空。|Le nom du groupe ne peut pas être vide.|Gruppenname darf nicht leer sein.
catalog.addGroup|Добавить группу|Add group|Añadir grupo|Adicionar grupo|添加分组|Ajouter un groupe|Gruppe hinzufügen
catalog.groupsSaved|Группы сохранены|Groups saved|Grupos guardados|Grupos salvos|分组已保存|Groupes enregistrés|Gruppen gespeichert
catalog.groupsError|Не удалось сохранить группы|Could not save groups|No se pudieron guardar los grupos|Não foi possível salvar os grupos|无法保存分组|Impossible d’enregistrer les groupes|Gruppen konnten nicht gespeichert werden
catalog.sectionError|Не удалось загрузить этот раздел|Could not load this section|No se pudo cargar esta sección|Não foi possível carregar esta seção|无法加载此分区|Impossible de charger cette section|Bereich konnte nicht geladen werden
catalog.managerError|Не удалось открыть управление тегами|Could not open tag management|No se pudo abrir la gestión de etiquetas|Não foi possível abrir o gerenciador de tags|无法打开标签管理|Impossible d’ouvrir la gestion des étiquettes|Tag-Verwaltung konnte nicht geöffnet werden
catalog.staleError|Не удалось обновить каталог. Показаны последние загруженные данные.|Could not refresh the catalog. Showing the last loaded data.|No se pudo actualizar el catálogo. Se muestran los últimos datos.|Não foi possível atualizar o catálogo. Mostrando os últimos dados.|无法刷新目录。正在显示上次加载的数据。|Impossible d’actualiser le catalogue. Affichage des dernières données.|Katalog konnte nicht aktualisiert werden. Zuletzt geladene Daten werden angezeigt.
catalog.otherTags|Другие теги: |Other tags: |Otras etiquetas: |Outras tags: |其他标签：|Autres étiquettes : |Weitere Tags: 
blockout.noGroup|Выберите группу для листа блокаута.|Select a group for the blockout sheet.|Elige un grupo para la hoja de bloques.|Selecione um grupo para a folha de blocagem.|请选择草模图板的分组。|Choisissez un groupe pour la planche de blockout.|Gruppe für die Blockout-Übersicht auswählen.
blockout.intro|Детали разложены по одной на общем столе.|Parts are arranged separately on one table.|Las piezas se disponen por separado en una mesa.|As peças são dispostas separadamente em uma mesa.|部件分别排列在同一桌面上。|Les pièces sont disposées séparément sur une table.|Teile sind einzeln auf einem gemeinsamen Tisch angeordnet.
blockout.table|3D-стол компонентов|3D component table|Mesa 3D de componentes|Mesa 3D de componentes|3D 组件桌面|Table 3D des composants|3D-Komponententisch
blockout.projections|Проекции листа блокаута|Blockout sheet projections|Proyecciones de la hoja de bloques|Projeções da folha de blocagem|草模图板投影|Projections de la planche de blockout|Projektionen der Blockout-Übersicht
blockout.breadcrumb| / лист блокаута| / blockout sheet| / hoja de bloques| / folha de blocagem| / 草模图板| / planche de blockout| / Blockout-Übersicht
blockout.components|Компоненты листа|Sheet components|Componentes de la hoja|Componentes da folha|图板组件|Composants de la planche|Komponenten der Übersicht
blockout.queueing|Добавляю в очередь…|Adding to queue…|Añadiendo a la cola…|Adicionando à fila…|正在加入队列…|Ajout à la file…|Wird in Warteschlange eingereiht…
blockout.building|Детали собираются…|Building parts…|Generando piezas…|Gerando peças…|正在构建部件…|Génération des pièces…|Teile werden erstellt…
blockout.unavailable|Сборка недоступна|Build unavailable|Generación no disponible|Geração indisponível|构建不可用|Génération indisponible|Build nicht verfügbar
blockout.snapshots|Создание снимков…|Creating snapshots…|Creando imágenes…|Criando imagens…|正在创建截图…|Création des captures…|Aufnahmen werden erstellt…
blockout.loadingParts|Загрузка списка деталей…|Loading part list…|Cargando lista de piezas…|Carregando lista de peças…|正在加载部件列表…|Chargement des pièces…|Teileliste wird geladen…
blockout.partsUnavailable|Список деталей недоступен|Part list unavailable|Lista de piezas no disponible|Lista de peças indisponível|部件列表不可用|Liste des pièces indisponible|Teileliste nicht verfügbar
blockout.assetsLabel|Ассеты:|Assets:|Recursos:|Assets:|资产：|Ressources :|Assets:
blockout.noVariant|нет варианта|No variant|Sin variante|Sem variante|无变体|Aucune variante|Keine Variante
blockout.empty|В этом листе пока нет компонентов.|This sheet has no components yet.|Esta hoja aún no tiene componentes.|Esta folha ainda não tem componentes.|此图板暂无组件。|Cette planche n’a aucun composant.|Diese Übersicht hat noch keine Komponenten.
blockout.retry|Повторите загрузку листа.|Reload the sheet.|Vuelve a cargar la hoja.|Recarregue a folha.|请重新加载图板。|Rechargez la planche.|Übersicht erneut laden.
blockout.views|Проекции листа|Sheet projections|Proyecciones de la hoja|Projeções da folha|图板投影|Projections de la planche|Projektionen der Übersicht
blockout.noModels|В этом листе пока нет собранных моделей.|No built models on this sheet yet.|Esta hoja aún no tiene modelos generados.|Esta folha ainda não tem modelos gerados.|此图板暂无已构建模型。|Aucun modèle généré sur cette planche.|Noch keine erstellten Modelle in dieser Übersicht.
blockout.error|Не удалось загрузить лист блокаута|Could not load the blockout sheet|No se pudo cargar la hoja de bloques|Não foi possível carregar a folha de blocagem|无法加载草模图板|Impossible de charger la planche de blockout|Blockout-Übersicht konnte nicht geladen werden
blockout.actionError|Не удалось выполнить действие|Could not complete the action|No se pudo completar la acción|Não foi possível concluir a ação|无法完成操作|Impossible d’effectuer cette action|Aktion konnte nicht abgeschlossen werden
blockout.alreadyOpen|Этот лист уже открыт в Blender.|This sheet is already open in Blender.|Esta hoja ya está abierta en Blender.|Esta folha já está aberta no Blender.|此图板已在 Blender 中打开。|Cette planche est déjà ouverte dans Blender.|Diese Übersicht ist bereits in Blender geöffnet.
blockout.prepared|Лист подготовлен. Можно скачать .blend.|The sheet is ready. Download the .blend file.|La hoja está lista. Descarga el archivo .blend.|A folha está pronta. Baixe o arquivo .blend.|图板已准备好。可以下载 .blend 文件。|La planche est prête. Téléchargez le fichier .blend.|Übersicht fertig. Die .blend-Datei kann heruntergeladen werden.
edit.quarterVoxel|0,25 м · воксель|0.25 m · voxel|0,25 m · voxel|0,25 m · voxel|0.25 米 · 体素|0,25 m · voxel|0,25 m · Voxel
edit.tenth|0,1 м|0.1 m|0,1 m|0,1 m|0.1 米|0,1 m|0,1 m
edit.half|0,5 м|0.5 m|0,5 m|0,5 m|0.5 米|0,5 m|0,5 m
tags.changeHelp|Переименование и удаление применяются ко всем связанным компонентам и ассетам.|Renaming and deletion apply to all related components and assets.|Renombrar y eliminar afecta a todos los componentes y recursos relacionados.|Renomear e excluir afeta todos os componentes e assets relacionados.|重命名和删除会影响所有关联组件和资产。|Le renommage et la suppression concernent tous les composants et ressources liés.|Umbenennen und Löschen betrifft alle zugehörigen Komponenten und Assets.
tags.mergeHelp|Тег с таким именем уже существует. Метки будут объединены без повторов.|A tag with this name exists. Tags will merge without duplicates.|Ya existe esta etiqueta. Se combinarán sin duplicados.|Esta tag já existe. As tags serão mescladas sem duplicatas.|此名称的标签已存在。标签将合并且不重复。|Cette étiquette existe déjà. Les étiquettes seront fusionnées sans doublons.|Dieser Tag existiert bereits. Tags werden ohne Duplikate zusammengeführt.
tags.refreshError|Тег изменён, но не удалось обновить карточки. Повторите загрузку или обновите страницу.|Tag changed, but cards could not refresh. Reload the list or page.|La etiqueta cambió, pero las tarjetas no se actualizaron. Recarga la lista o página.|A tag mudou, mas os cartões não atualizaram. Recarregue a lista ou página.|标签已更改，但卡片未能刷新。请重新加载列表或页面。|Étiquette modifiée, mais cartes non actualisées. Rechargez la liste ou la page.|Tag geändert, Karten nicht aktualisiert. Liste oder Seite neu laden.
tags.catalogRefreshError|Изменение сохранено, но не удалось обновить каталог. Закройте окно и обновите страницу.|Change saved, but the catalog could not refresh. Close the dialog and reload.|Cambio guardado, pero el catálogo no se actualizó. Cierra la ventana y recarga.|Alteração salva, mas o catálogo não atualizou. Feche a janela e recarregue.|更改已保存，但目录未能刷新。请关闭对话框并重新加载。|Modification enregistrée, mais catalogue non actualisé. Fermez et rechargez.|Änderung gespeichert, Katalog nicht aktualisiert. Dialog schließen und neu laden.
error.oldApi|Запущена старая версия API без управления тегами. Перезапустите сервер реестра и повторите загрузку.|This API version lacks tag management. Restart the registry server and reload.|Esta API no admite gestión de etiquetas. Reinicia el servidor y recarga.|Esta API não tem gerenciamento de tags. Reinicie o servidor e recarregue.|此 API 版本不支持标签管理。请重启注册表服务器并重新加载。|Cette API ne gère pas les étiquettes. Redémarrez le serveur et rechargez.|Diese API-Version bietet keine Tag-Verwaltung. Registry-Server neu starten und neu laden.
blockout.chooseAssetHelp|Детали разложены по одной на общем столе. Выберите ассет, чтобы использовать его варианты компонентов.|Parts are arranged on one table. Select an asset to use its component variants.|Las piezas se disponen en una mesa. Elige un recurso para usar sus variantes.|As peças são dispostas em uma mesa. Selecione um asset para usar suas variantes.|部件排列在同一桌面。选择资产以使用其组件变体。|Les pièces sont disposées sur une table. Choisissez une ressource pour ses variantes.|Teile liegen auf einem Tisch. Asset wählen, um dessen Komponentenvarianten zu verwenden.
blockout.buildFirst|Для открытия листа в Blender сначала соберите отсутствующие детали.|Build the missing parts before opening the sheet in Blender.|Genera las piezas que faltan antes de abrir la hoja en Blender.|Gere as peças ausentes antes de abrir a folha no Blender.|在 Blender 中打开图板前，请先构建缺失的部件。|Générez les pièces manquantes avant d’ouvrir la planche dans Blender.|Fehlende Teile vor dem Öffnen der Übersicht in Blender erstellen.
blockout.viewHelp|Шесть ортографических ракурсов в одном масштабе и изометрия. Нажмите снимок, чтобы открыть PNG.|Six orthographic views at one scale and an isometric view. Click to open the PNG.|Seis vistas ortográficas a igual escala y una isométrica. Haz clic para abrir el PNG.|Seis vistas ortográficas na mesma escala e uma isométrica. Clique para abrir o PNG.|六个相同缩放的正交视图和一个等轴测视图。点击打开 PNG。|Six vues orthographiques à la même échelle et une isométrie. Cliquez pour ouvrir le PNG.|Sechs orthografische Ansichten im gleichen Maßstab und eine Isometrie. Klicken öffnet das PNG.
blockout.retryParts|Повторите загрузку, чтобы увидеть детали на столе.|Reload to see the parts on the table.|Recarga para ver las piezas en la mesa.|Recarregue para ver as peças na mesa.|请重新加载以查看桌面部件。|Rechargez pour voir les pièces sur la table.|Neu laden, um die Teile auf dem Tisch zu sehen.
blockout.queuedNotice|Детали добавлены в очередь. Лист обновится после сборки.|Parts queued. The sheet will update after the build.|Piezas en cola. La hoja se actualizará tras la generación.|Peças na fila. A folha atualizará após a geração.|部件已排队。构建后图板将更新。|Pièces en attente. La planche sera actualisée après génération.|Teile eingereiht. Übersicht wird nach dem Build aktualisiert.
blockout.allBuilt|Все доступные детали уже собраны или находятся в очереди.|All available parts are built or queued.|Todas las piezas disponibles están generadas o en cola.|Todas as peças disponíveis estão geradas ou na fila.|全部可用部件已构建或已排队。|Toutes les pièces sont générées ou en attente.|Alle verfügbaren Teile sind erstellt oder eingereiht.
blockout.readyNotice|Снимки готовы: сверху, снизу, спереди, сзади, справа, слева и изометрия.|Snapshots ready: top, bottom, front, back, right, left and isometric.|Imágenes listas: superior, inferior, frontal, trasera, derecha, izquierda e isométrica.|Imagens prontas: superior, inferior, frente, trás, direita, esquerda e isométrica.|截图已就绪：顶视、底视、前视、后视、右视、左视及等轴测。|Captures prêtes : dessus, dessous, face, dos, droite, gauche et isométrie.|Aufnahmen fertig: oben, unten, vorne, hinten, rechts, links und Isometrie.
blockout.openNotice|Лист открыт в Blender. Теперь можно собрать ассет вручную.|The sheet is open in Blender. You can assemble the asset manually.|La hoja está abierta en Blender. Puedes ensamblar el recurso manualmente.|A folha está aberta no Blender. Você pode montar o asset manualmente.|图板已在 Blender 中打开。现在可以手动组装资产。|La planche est ouverte dans Blender. Assemblez la ressource manuellement.|Übersicht in Blender geöffnet. Das Asset kann nun manuell zusammengestellt werden.
blockout.groupHint|Лист блокаута для группы|Blockout sheet for this group|Hoja de bloques del grupo|Folha de blocagem do grupo|此分组的草模图板|Planche de blockout du groupe|Blockout-Übersicht dieser Gruppe
blockout.loadingLink|Лист блокаута…|Blockout sheet…|Hoja de bloques…|Folha de blocagem…|草模图板…|Planche de blockout…|Blockout-Übersicht…
projections.tooltip|PNG сверху, снизу, спереди, сзади, справа и слева|PNG: top, bottom, front, back, right and left|PNG: superior, inferior, frontal, trasera, derecha e izquierda|PNG: superior, inferior, frente, trás, direita e esquerda|PNG：顶视、底视、前视、后视、右视及左视|PNG : dessus, dessous, face, dos, droite et gauche|PNG: oben, unten, vorne, hinten, rechts und links
blender.forkAssetHelp|Новый дочерний вариант: вся композиция в .blend, каждая деталь — отдельный объект; откроется в Blender|New child variant: the assembly in a .blend, each part a separate object; opens in Blender|Nueva variante hija: ensamblaje en .blend, cada pieza como objeto; se abre en Blender|Nova variante filha: montagem em .blend, cada peça como objeto; abre no Blender|新建子变体：将组合保存为 .blend，每个部件为独立对象；在 Blender 中打开|Nouvelle variante enfant : assemblage en .blend, pièces séparées ; s’ouvre dans Blender|Neue untergeordnete Variante: Zusammenbau als .blend mit einzelnen Teilen; öffnet in Blender
blender.forkComponentHelp|Новый дочерний вариант с копией этой модели в .blend; откроется в Blender|New child variant with a copy of this model in a .blend; opens in Blender|Nueva variante hija con una copia en .blend; se abre en Blender|Nova variante filha com cópia em .blend; abre no Blender|新建子变体并将此模型复制为 .blend；在 Blender 中打开|Nouvelle variante enfant avec une copie en .blend ; s’ouvre dans Blender|Neue untergeordnete Variante mit Modellkopie als .blend; öffnet in Blender
catalog.abstractBases|Абстрактные базы (только для наследования): |Abstract bases (inheritance only): |Bases abstractas (solo herencia): |Bases abstratas (apenas herança): |抽象基础（仅用于继承）：|Bases abstraites (héritage uniquement) : |Abstrakte Basen (nur für Vererbung): 
common.retryAction|повторите действие|Retry the action|Reintenta la acción|Tente a ação novamente|请重试操作|Réessayez l’action|Aktion erneut versuchen
dynamic.created|Создан {ref}, сборка в очереди|Created {ref}, build queued|Creado {ref}, generación en cola|Criado {ref}, geração na fila|已创建 {ref}，构建已排队|{ref} créé, génération en attente|{ref} erstellt, Build eingereiht
dynamic.compare|Сравнение {a} ↔ {b}|Compare {a} ↔ {b}|Comparar {a} ↔ {b}|Comparar {a} ↔ {b}|比较 {a} ↔ {b}|Comparer {a} ↔ {b}|Vergleich {a} ↔ {b}
dynamic.diff|Дифф параметров: {count} различ.|Parameter differences: {count}|Diferencias de parámetros: {count}|Diferenças de parâmetros: {count}|参数差异：{count}|Différences de paramètres : {count}|Parameterunterschiede: {count}
dynamic.chain| · цепочка {chain}| · chain {chain}| · cadena {chain}| · cadeia {chain}| · 链 {chain}| · chaîne {chain}| · Kette {chain}
dynamic.inheritance|наследование: {chain}|Inheritance: {chain}|Herencia: {chain}|Herança: {chain}|继承：{chain}|Héritage : {chain}|Vererbung: {chain}
dynamic.mounts| · крепится на: {mounts}| · mounts on: {mounts}| · se fija a: {mounts}| · fixa em: {mounts}| · 可连接：{mounts}| · se fixe sur : {mounts}| · wird befestigt an: {mounts}
dynamic.from|из {source}|From {source}|De {source}|De {source}|来自 {source}|De {source}|Aus {source}
dynamic.branchTitle|Ветка от {ref}|Branch from {ref}|Rama desde {ref}|Ramificação de {ref}|从 {ref} 创建分支|Branche de {ref}|Verzweigung von {ref}
dynamic.parentHelp|Родитель: {parent}. В delta попадут только изменённые поля.|Parent: {parent}. Only changed fields are saved in delta.|Padre: {parent}. Solo los campos cambiados se guardan en delta.|Pai: {parent}. Apenas campos alterados são salvos em delta.|父变体：{parent}。delta 仅保存更改字段。|Parent : {parent}. Seuls les champs modifiés entrent dans delta.|Vorgänger: {parent}. Nur geänderte Felder werden in delta gespeichert.
dynamic.catalogCount|Показано {shown} из {total}|Showing {shown} of {total}|Mostrando {shown} de {total}|Mostrando {shown} de {total}|显示 {shown}／{total}|Affichage de {shown} sur {total}|{shown} von {total} angezeigt
dynamic.moreTags|Ещё {count} тегов|More tags: {count}|Más etiquetas: {count}|Mais tags: {count}|更多标签：{count}|Autres étiquettes : {count}|Weitere Tags: {count}
dynamic.items|{count} шт.|Items: {count}|Elementos: {count}|Itens: {count}|条目：{count}|Éléments : {count}|Einträge: {count}
dynamic.groupExists|Группа {id} уже существует.|Group {id} already exists.|El grupo {id} ya existe.|O grupo {id} já existe.|分组 {id} 已存在。|Le groupe {id} existe déjà.|Gruppe {id} existiert bereits.
dynamic.groupName|Название группы {id}|Name of group {id}|Nombre del grupo {id}|Nome do grupo {id}|分组 {id} 的名称|Nom du groupe {id}|Name der Gruppe {id}
dynamic.deleteGroup|Удалить группу {name}|Delete group {name}|Eliminar grupo {name}|Excluir grupo {name}|删除分组 {name}|Supprimer le groupe {name}|Gruppe {name} löschen
dynamic.composeTitle|Сборка: {title}|Assembly: {title}|Ensamblaje: {title}|Montagem: {title}|组装：{title}|Assemblage : {title}|Zusammenbau: {title}
dynamic.socket|сокет {name} (на структуре)|Socket {name} (on structure)|Anclaje {name} (en estructura)|Socket {name} (na estrutura)|连接点 {name}（位于结构上）|Socket {name} (sur structure)|Socket {name} (an Struktur)
dynamic.bodySocket|сокет корпуса: {name}|Body socket: {name}|Anclaje del cuerpo: {name}|Socket do corpo: {name}|主体连接点：{name}|Socket du corps : {name}|Körper-Socket: {name}
dynamic.accepts| · принимает: {accepts} · max_grid {grid}| · accepts: {accepts} · max_grid {grid}| · admite: {accepts} · max_grid {grid}| · aceita: {accepts} · max_grid {grid}| · 接受：{accepts} · max_grid {grid}| · accepte : {accepts} · max_grid {grid}| · akzeptiert: {accepts} · max_grid {grid}
dynamic.previous|было: {value}|Previously: {value}|Antes: {value}|Antes: {value}|之前：{value}|Avant : {value}|Zuvor: {value}
dynamic.incompatible|{ref} (не собран / несовместим)|{ref} (not built / incompatible)|{ref} (no generado / incompatible)|{ref} (não gerado / incompatível)|{ref}（未构建／不兼容）|{ref} (non généré / incompatible)|{ref} (nicht erstellt / inkompatibel)
dynamic.slotVariant|Вариант для слота {name}|Variant for slot {name}|Variante de ranura {name}|Variante do slot {name}|插槽 {name} 的变体|Variante de l’emplacement {name}|Variante für Slot {name}
dynamic.partNumber|Деталь {number}|Part {number}|Pieza {number}|Peça {number}|部件 {number}|Pièce {number}|Teil {number}
dynamic.attachment| · {grid} vox · крепление: {mounts}| · {grid} vox · attachment: {mounts}| · {grid} vox · anclaje: {mounts}| · {grid} vox · fixação: {mounts}| · {grid} vox · 连接：{mounts}| · {grid} vox · fixation : {mounts}| · {grid} vox · Befestigung: {mounts}
dynamic.slotInvalidName|Слот {name}: неверное имя.|Slot {name}: invalid name.|Ranura {name}: nombre no válido.|Slot {name}: nome inválido.|插槽 {name}：名称无效。|Emplacement {name} : nom invalide.|Slot {name}: ungültiger Name.
dynamic.slotDuplicate|Имя слота {name} повторяется.|Duplicate slot name: {name}.|Nombre de ranura duplicado: {name}.|Nome de slot duplicado: {name}.|插槽名称重复：{name}。|Nom d’emplacement dupliqué : {name}.|Doppelter Slot-Name: {name}.
dynamic.slotChoose|Слот {name}: выберите готовый вариант.|Slot {name}: select a built variant.|Ranura {name}: elige una variante generada.|Slot {name}: selecione uma variante gerada.|插槽 {name}：请选择已构建变体。|Emplacement {name} : choisissez une variante générée.|Slot {name}: erstellte Variante wählen.
dynamic.slotChooseSocket|Слот {name}: выберите сокет крепления.|Slot {name}: select an attachment socket.|Ranura {name}: elige un anclaje.|Slot {name}: selecione um socket de fixação.|插槽 {name}：请选择连接点。|Emplacement {name} : choisissez un socket de fixation.|Slot {name}: Befestigungs-Socket wählen.
dynamic.slotIncompatible|Слот {name}: сокет родителя несовместим с выбранной моделью.|Slot {name}: parent socket is incompatible with the selected model.|Ranura {name}: el anclaje padre no es compatible con el modelo.|Slot {name}: o socket pai é incompatível com o modelo.|插槽 {name}：父连接点与所选模型不兼容。|Emplacement {name} : le socket parent est incompatible avec ce modèle.|Slot {name}: Vorgänger-Socket ist mit dem Modell inkompatibel.
dynamic.slotOffset|Слот {name}: смещение должно быть в пределах ±10 м.|Slot {name}: offset must be within ±10 m.|Ranura {name}: desplazamiento dentro de ±10 m.|Slot {name}: deslocamento dentro de ±10 m.|插槽 {name}：偏移须在 ±10 米内。|Emplacement {name} : décalage limité à ±10 m.|Slot {name}: Versatz muss innerhalb ±10 m liegen.
dynamic.preview|превью: {ref}|Preview: {ref}|Vista previa: {ref}|Prévia: {ref}|预览：{ref}|Aperçu : {ref}|Vorschau: {ref}
dynamic.changedFields|изменено: {fields}|Changed: {fields}|Cambiado: {fields}|Alterado: {fields}|已更改：{fields}|Modifié : {fields}|Geändert: {fields}
dynamic.savedMaterial|Сохранён {ref}; Blender-превью в очереди|Saved {ref}; Blender preview queued|Guardado {ref}; vista Blender en cola|Salvo {ref}; prévia Blender na fila|已保存 {ref}；Blender 预览已排队|{ref} enregistré ; aperçu Blender en attente|{ref} gespeichert; Blender-Vorschau eingereiht
dynamic.blenderRender|Blender-рендер {ref}: {state}|Blender render {ref}: {state}|Renderizado Blender {ref}: {state}|Renderização Blender {ref}: {state}|Blender 渲染 {ref}：{state}|Rendu Blender {ref} : {state}|Blender-Rendering {ref}: {state}
dynamic.glbError|Не удалось загрузить GLB: {error}|Could not load GLB: {error}|No se pudo cargar GLB: {error}|Não foi possível carregar GLB: {error}|无法加载 GLB：{error}|Impossible de charger le GLB : {error}|GLB konnte nicht geladen werden: {error}
dynamic.openPng|Открыть PNG: {view}|Open PNG: {view}|Abrir PNG: {view}|Abrir PNG: {view}|打开 PNG：{view}|Ouvrir le PNG : {view}|PNG öffnen: {view}
dynamic.rating|рейтинг {value}/5|Rating {value}/5|Valoración {value}/5|Avaliação {value}/5|评分 {value}/5|Note {value}/5|Bewertung {value}/5
dynamic.setRating|Оценить на {value} из 5|Rate {value} out of 5|Valorar {value} de 5|Avaliar {value} de 5|评为 {value}／5|Noter {value} sur 5|Mit {value} von 5 bewerten
dynamic.buildState|сборка: {state}|Build: {state}|Generación: {state}|Geração: {state}|构建：{state}|Génération : {state}|Build: {state}
dynamic.editTitle|Размещение: {title}|Placement: {title}|Posición: {title}|Posicionamento: {title}|放置：{title}|Placement : {title}|Platzierung: {title}
dynamic.offsetRange|Смещение по каждой оси должно быть в пределах ±{max} м.|Offset on each axis must be within ±{max} m.|El desplazamiento en cada eje debe estar dentro de ±{max} m.|O deslocamento em cada eixo deve estar dentro de ±{max} m.|每个轴的偏移须在 ±{max} 米内。|Le décalage sur chaque axe doit rester dans ±{max} m.|Versatz jeder Achse muss innerhalb ±{max} m liegen.
dynamic.changedSlots|Изменено слотов: {count}. Сдвиг виден в предпросмотре.|Changed slots: {count}. The preview shows the offset.|Ranuras cambiadas: {count}. El desplazamiento aparece en la vista previa.|Slots alterados: {count}. O deslocamento aparece na prévia.|已更改插槽：{count}。预览显示偏移。|Emplacements modifiés : {count}. Le décalage apparaît dans l’aperçu.|Geänderte Slots: {count}. Versatz wird in der Vorschau angezeigt.
dynamic.host|Хост: {host}. Дочерние слоты перемещаются вместе с ним.|Host: {host}. Child slots move with it.|Anfitrión: {host}. Las ranuras hijas se mueven con él.|Host: {host}. Slots filhos se movem com ele.|宿主：{host}。子插槽随其一起移动。|Hôte : {host}. Les enfants se déplacent avec lui.|Host: {host}. Untergeordnete Slots werden mitverschoben.
dynamic.meters|{axis}, метры|{axis}, meters|{axis}, metros|{axis}, metros|{axis}，米|{axis}, mètres|{axis}, Meter
dynamic.sheetTitle|Лист блокаута · {title}|Blockout sheet · {title}|Hoja de bloques · {title}|Folha de blocagem · {title}|草模图板 · {title}|Planche de blockout · {title}|Blockout-Übersicht · {title}
dynamic.sheetAsset|Детали ассета {id} · {vid} разложены по одной на общем столе.|Parts of {id} · {vid} are arranged separately on one table.|Piezas de {id} · {vid} dispuestas en una mesa.|Peças de {id} · {vid} dispostas em uma mesa.|{id} · {vid} 的部件分别排列在同一桌面。|Pièces de {id} · {vid} disposées sur une table.|Teile von {id} · {vid} sind einzeln auf einem Tisch angeordnet.
dynamic.buildParts|Собрать детали ({count})|Build parts ({count})|Generar piezas ({count})|Gerar peças ({count})|构建部件（{count}）|Générer les pièces ({count})|Teile erstellen ({count})
dynamic.readyParts|Готово {ready} из {total} деталей|Parts ready: {ready} of {total}|Piezas listas: {ready} de {total}|Peças prontas: {ready} de {total}|部件就绪：{ready}／{total}|Pièces prêtes : {ready} sur {total}|Teile fertig: {ready} von {total}
dynamic.queueSuffix| · в очереди и работе: {count}| · queued or building: {count}| · en cola o generando: {count}| · na fila ou gerando: {count}| · 排队或构建中：{count}| · en attente ou génération : {count}| · eingereiht oder im Build: {count}
dynamic.partReuse|В ассете используется {count} раза|Uses in asset: {count}|Usos en el recurso: {count}|Usos no asset: {count}|资产中使用次数：{count}|Utilisations dans la ressource : {count}|Verwendungen im Asset: {count}
dynamic.tagCount|{visible} из {total} тегов|Tags: {visible} of {total}|Etiquetas: {visible} de {total}|Tags: {visible} de {total}|标签：{visible}／{total}|Étiquettes : {visible} sur {total}|Tags: {visible} von {total}
dynamic.deleteTag|Удалить тег «{name}» у всех?|Remove tag “{name}” from all entries?|¿Quitar la etiqueta «{name}» de todas las entradas?|Remover a tag “{name}” de todas as entradas?|从全部条目移除标签“{name}”？|Retirer l’étiquette « {name} » partout ?|Tag „{name}“ überall entfernen?
dynamic.blendPreparing|Готовлю .blend из {ref}…|Preparing .blend from {ref}…|Preparando .blend desde {ref}…|Preparando .blend de {ref}…|正在从 {ref} 准备 .blend…|Préparation du .blend de {ref}…|.blend aus {ref} wird vorbereitet…
dynamic.blendOpen|{ref} открыт в Blender|{ref} opened in Blender|{ref} abierto en Blender|{ref} aberto no Blender|{ref} 已在 Blender 中打开|{ref} ouvert dans Blender|{ref} in Blender geöffnet
dynamic.blendAlready|{ref} уже открыт в Blender|{ref} already open in Blender|{ref} ya está abierto en Blender|{ref} já está aberto no Blender|{ref} 已经在 Blender 中打开|{ref} déjà ouvert dans Blender|{ref} bereits in Blender geöffnet
dynamic.blendError|{ref}: Blender не открылся — {error}|{ref}: Blender did not open — {error}|{ref}: Blender no se abrió — {error}|{ref}: Blender não abriu — {error}|{ref}：Blender 未能打开 — {error}|{ref} : Blender non ouvert — {error}|{ref}: Blender wurde nicht geöffnet — {error}
dynamic.rebuild|Пересборка {ref}: {state}|Rebuild {ref}: {state}|Regeneración {ref}: {state}|Nova geração {ref}: {state}|重新构建 {ref}：{state}|Regénération {ref} : {state}|Neuer Build {ref}: {state}
dynamic.cannotBuild|Не собрать: {error}|Cannot build: {error}|No se puede generar: {error}|Não é possível gerar: {error}|无法构建：{error}|Génération impossible : {error}|Build nicht möglich: {error}
dynamic.buildFailed|ошибка сборки — {error}|Build failed — {error}|Error de generación — {error}|Falha na geração — {error}|构建失败 — {error}|Échec de génération — {error}|Build fehlgeschlagen — {error}
dynamic.tableHint|Компоненты {title} на общем столе|Components of {title} on one table|Componentes de {title} en una mesa|Componentes de {title} em uma mesa|{title} 的组件在同一桌面|Composants de {title} sur une table|Komponenten von {title} auf einem Tisch
dynamic.sheetLink|Лист: {title}|Sheet: {title}|Hoja: {title}|Folha: {title}|图板：{title}|Planche : {title}|Übersicht: {title}
dynamic.blendContinue|Продолжить правку {file}|Continue editing {file}|Continuar editando {file}|Continuar editando {file}|继续编辑 {file}|Continuer la modification de {file}|{file} weiter bearbeiten
dynamic.manualGeometry|Ручная геометрия: {file}. |Manual geometry: {file}. |Geometría manual: {file}. |Geometria manual: {file}. |手动几何：{file}。|Géométrie manuelle : {file}. |Manuelle Geometrie: {file}. 
dynamic.treeHint|клик — выбрать, Shift+клик — сравнить|Click to select, Shift+click to compare|Clic para elegir, Mayús+clic para comparar|Clique para selecionar, Shift+clique para comparar|单击选择，Shift+单击比较|Clic pour sélectionner, Maj+clic pour comparer|Klick zum Auswählen, Umschalt+Klick zum Vergleichen
dynamic.structure|Структура · {status}|Structure · {status}|Estructura · {status}|Estrutura · {status}|结构 · {status}|Structure · {status}|Struktur · {status}
dynamic.relationships|{verified} связей · {issues} проблем · |Relationships: {verified} · issues: {issues} · |Relaciones: {verified} · problemas: {issues} · |Relações: {verified} · problemas: {issues} · |关系：{verified} · 问题：{issues} · |Relations : {verified} · problèmes : {issues} · |Beziehungen: {verified} · Probleme: {issues} · 
dynamic.primaryMass|Масса: {mass} · акцент: {hero}|Mass: {mass} · focal feature: {hero}|Masa: {mass} · foco: {hero}|Massa: {mass} · destaque: {hero}|体块：{mass} · 重点：{hero}|Masse : {mass} · élément principal : {hero}|Masse: {mass} · Hauptmerkmal: {hero}
dynamic.secondary|Вторичные: {parts} · спокойные зоны: {zones}|Secondary: {parts} · quiet zones: {zones}|Secundarios: {parts} · zonas tranquilas: {zones}|Secundários: {parts} · zonas calmas: {zones}|次要部件：{parts} · 留白区：{zones}|Secondaires : {parts} · zones calmes : {zones}|Nebenmerkmale: {parts} · ruhige Bereiche: {zones}
dynamic.density|Крупные детали: {parts} · крыша: {roof}% · фасад: {front}% · свободные сокеты: {free}%|Large parts: {parts} · roof: {roof}% · front: {front}% · free sockets: {free}%|Piezas grandes: {parts} · techo: {roof}% · frente: {front}% · anclajes libres: {free}%|Peças grandes: {parts} · teto: {roof}% · frente: {front}% · sockets livres: {free}%|大型部件：{parts} · 屋顶：{roof}% · 正面：{front}% · 空闲连接点：{free}%|Grandes pièces : {parts} · toit : {roof}% · façade : {front}% · sockets libres : {free}%|Große Teile: {parts} · Dach: {roof}% · Vorderseite: {front}% · freie Sockets: {free}%
dynamic.slotParams|{name}: параметры {ref}|{name}: parameters {ref}|{name}: parámetros {ref}|{name}: parâmetros {ref}|{name}：参数 {ref}|{name} : paramètres {ref}|{name}: Parameter {ref}
dynamic.sheetBlenderHelp|В Blender выберите все объекты детали в её коллекции. Shift+D — копия, G — перемещение; шаг сетки {grid} м.|In Blender, select all objects in the part’s collection. Shift+D duplicates, G moves; grid step {grid} m.|En Blender, selecciona los objetos de la colección. Mayús+D duplica, G mueve; paso {grid} m.|No Blender, selecione os objetos da coleção. Shift+D duplica, G move; passo {grid} m.|在 Blender 中选择部件集合的全部对象。Shift+D 复制，G 移动；网格步长 {grid} 米。|Dans Blender, sélectionnez les objets de la collection. Maj+D duplique, G déplace ; pas {grid} m.|In Blender alle Objekte der Teilsammlung auswählen. Umschalt+D dupliziert, G verschiebt; Rasterschritt {grid} m.
dynamic.sheetQueueError|Не удалось поставить часть деталей в очередь: {error}|Some parts could not be queued: {error}|No se pudieron poner piezas en cola: {error}|Não foi possível colocar algumas peças na fila: {error}|部分部件无法加入队列：{error}|Certaines pièces n’ont pas été mises en attente : {error}|Einige Teile konnten nicht eingereiht werden: {error}
dynamic.sheetOpenError|Лист подготовлен, но Blender не удалось открыть: {error}. Можно скачать .blend.|The sheet is ready, but Blender did not open: {error}. Download the .blend.|La hoja está lista, pero Blender no se abrió: {error}. Descarga el .blend.|A folha está pronta, mas Blender não abriu: {error}. Baixe o .blend.|图板已准备好，但 Blender 未打开：{error}。可以下载 .blend。|Planche prête, mais Blender non ouvert : {error}. Téléchargez le .blend.|Übersicht fertig, Blender nicht geöffnet: {error}. .blend-Datei herunterladen.
dynamic.noEditVariant|У ассета {id} пока нет варианта для редактирования|Asset {id} has no variant to edit yet|El recurso {id} aún no tiene variante para editar|O asset {id} ainda não tem variante para editar|资产 {id} 暂无可编辑变体|La ressource {id} n’a aucune variante à modifier|Asset {id} hat noch keine bearbeitbare Variante
dynamic.placementSuffix| · размещение| · placement| · posición| · posicionamento| · 放置| · placement| · Platzierung
dynamic.plainSocket|сокет {name}|Socket {name}|Anclaje {name}|Socket {name}|连接点 {name}|Socket {name}|Socket {name}
dynamic.tagRelations|Связано сущностей: {entities} · меток в вариантах: {variants}|Related entities: {entities} · variant tags: {variants}|Entidades relacionadas: {entities} · etiquetas de variantes: {variants}|Entidades relacionadas: {entities} · tags de variantes: {variants}|关联实体：{entities} · 变体标签：{variants}|Entités liées : {entities} · étiquettes de variantes : {variants}|Zugehörige Einträge: {entities} · Varianten-Tags: {variants}
dynamic.tagRemovalHelp|Тег будет убран из метаданных связанных компонентов, ассетов, вариантов и списка важных тегов.|The tag will be removed from related components, assets, variants and priority tag settings.|La etiqueta se quitará de componentes, recursos, variantes y ajustes relacionados.|A tag será removida de componentes, assets, variantes e configurações relacionadas.|标签将从关联组件、资产、变体及优先标签设置中移除。|L’étiquette sera retirée des composants, ressources, variantes et réglages liés.|Tag wird aus zugehörigen Komponenten, Assets, Varianten und Einstellungen entfernt.
dynamic.tagRemoved|Тег «{name}» удалён|Tag “{name}” removed|Etiqueta «{name}» eliminada|Tag “{name}” removida|标签“{name}”已移除|Étiquette « {name} » retirée|Tag „{name}“ entfernt
dynamic.tagRenamed|Тег «{old}» переименован в «{name}»|Tag “{old}” renamed to “{name}”|Etiqueta «{old}» renombrada a «{name}»|Tag “{old}” renomeada para “{name}”|标签“{old}”已重命名为“{name}”|Étiquette « {old} » renommée « {name} »|Tag „{old}“ in „{name}“ umbenannt
dynamic.tagsUpdated|{message}. Обновлено сущностей: {entities}, вариантов: {variants}.|{message}. Updated entities: {entities}, variants: {variants}.|{message}. Entidades actualizadas: {entities}, variantes: {variants}.|{message}. Entidades atualizadas: {entities}, variantes: {variants}.|{message}。已更新实体：{entities}，变体：{variants}。|{message}. Entités actualisées : {entities}, variantes : {variants}.|{message}. Aktualisierte Einträge: {entities}, Varianten: {variants}.
experimental.proportions|Пропорции|Proportions|||||
experimental.head|Голова|Head|||||
experimental.hair|Волосы|Hair|||||
experimental.outfit|Одежда|Outfit|||||
experimental.palette|Палитра|Palette|||||
experimental.onlyLeft|Только слева|Left only|||||
experimental.sideBySide|Рядом|Side by side|||||
experimental.overlay|Наложение|Overlay|||||
experimental.wires|Каркасы|Wireframes|||||
experimental.visualReference|визуальный референс|Visual reference|||||
experimental.topology|изучение топологии|Topology study|||||
experimental.derivative|производные|Derivatives|||||
experimental.productionTemplate|production-шаблон|Production template|||||
experimental.noReferences|Референсов нет. Импорт: |No references. Import: |||||
experimental.normalized|Референс · нормализован (T-поза)|Reference · normalized (T-pose)|||||
experimental.regions|Референс · семантические регионы|Reference · semantic regions|||||
experimental.bone|Кость для режима Weights|Bone for Weights mode|||||
experimental.opacityHint|Прозрачность правой модели (наложение, силуэт, каркасы)|Right model opacity (overlay, silhouette, wireframes)|||||
experimental.noCompare|— без сравнения —|— no comparison —|||||
experimental.isolate|Изолировать|Isolate|||||
experimental.frame|Кадр по мешу|Frame mesh|||||
experimental.meshes|Меши|Meshes|||||
experimental.showAll|Показать все|Show all|||||
experimental.mesh|меш|Mesh|||||
experimental.glbCounts|GLB триангулирован и режет вершины по швам: точные счётчики исходника — в «Анализе» ниже.|GLB is triangulated and splits seam vertices; exact source counts are in Analysis below.|||||
experimental.leftSuffix|  · слева|  · left|||||
experimental.rightSuffix|  · справа|  · right|||||
experimental.noArmature|armature: нет (не скинован)|Armature: no (not skinned)|||||
experimental.vertexColors|вершинные цвета: да (палитра / регионы)|Vertex colors: yes (palette / regions)|||||
experimental.noVertexColors|вершинных цветов нет|No vertex colors|||||
experimental.sourceAnalysis|Анализ исходника|Source analysis|||||
experimental.noAnalysis|Нет analysis.json — запустите \`python -m registry reference build\`.|No analysis.json — run \`python -m registry reference build\`.|||||
experimental.rights|Права (reference.yaml)|Rights (reference.yaml)|||||
experimental.unspecified|не указана|Unspecified|||||
experimental.rightsHelp|Права меняет только человек. Шаблон извлекается, лишь когда разрешены производные и production.|Only a person changes rights. Extraction requires derivative and production permissions.|||||
experimental.semantics|Семантическая разметка|Semantic annotations|||||
experimental.noSemantics|Нет semantic.yaml — см. semantic.suggested.yaml в папке референса.|No semantic.yaml — see semantic.suggested.yaml in the reference folder.|||||
experimental.templatesFromReference|Шаблоны из этого референса|Templates from this reference|||||
experimental.noTemplates|Ещё нет. \`python -m registry template extract |None yet. \`python -m registry template extract |||||
experimental.referenceHelp|R&D: внешние меши для изучения и шаблонов Character Factory V2. references/ в игру не экспортируется.|R&D: external meshes for study and Character Factory V2 templates. references/ is not exported to games.|||||
experimental.references|Референсы|References|||||
experimental.templates|Шаблоны|Templates|||||
experimental.opacity|прозрачность правой модели|Right model opacity|||||
experimental.sceneHelp|Одна сцена: одна ортокамера, один свет и земля, поза покоя (клипы не играют). |One scene: orthographic camera, light, ground and rest pose (clips do not play). |||||
experimental.weightsHelp|Weights — тепловая карта выбранной кости; у нескинованного меша показываются его вершинные цвета (регионы).|Weights shows the selected bone’s heat map; unskinned meshes show vertex colors (regions).|||||
experimental.catalogHint|Референсы, шаблоны и сравнение с персонажами|References, templates and character comparisons|||||
experimental.castBreadcrumb| / каст| / cast|||||
experimental.castSource| · источник: registry/characters/cast.yaml| · source: registry/characters/cast.yaml|||||
experimental.castMissing|Не собраны: |Not built: |||||
experimental.castSkipped| — они не попадут в сцену.| — excluded from the scene.|||||
legacy.hint|модели, сделанные до реестра|Models created before the registry|||||
legacy.rendering|рендер…|Rendering…|||||
legacy.animatedHint|в файле есть анимация|File contains animation|||||
legacy.search|поиск по имени и папке|Search by name and folder|||||
legacy.sources|все источники|All sources|||||
legacy.formatsAll|любой формат|Any format|||||
legacy.animated|▶ с анимацией|▶ Animated|||||
legacy.root|(корень)|(root)|||||
legacy.help|Модели, сделанные до реестра. Только просмотр: исходные файлы не меняются, Blender рендерит снимки в build/legacy/.|Models predating the registry. Read-only: source files stay intact; Blender renders snapshots to build/legacy/.|||||
legacy.render|Отрендерить|Render|||||
legacy.rerender|Перерендерить|Render again|||||
legacy.copyPath|скопировать путь к файлу|Copy file path|||||
legacy.path|Путь ⧉|Path ⧉|||||
legacy.file|Файл|File|||||
legacy.formats|форматы|Formats|||||
legacy.renderFrom|рендер из|Render from|||||
legacy.size|размер|Size|||||
legacy.modified|изменён|Modified|||||
legacy.version|версия файла|File version|||||
legacy.scene|сцена|Scene|||||
legacy.geometry|Геометрия|Geometry|||||
legacy.objects|объекты|Objects|||||
legacy.preview|Превью (Blender)|Preview (Blender)|||||
legacy.openError|Не удалось открыть файл|Could not open the file|||||
legacy.notRendered|Ещё не отрендерено|Not rendered yet|||||
legacy.pathCopied|Путь скопирован|Path copied|||||
legacy.previous|предыдущая (←)|Previous (←)|||||
legacy.next|следующая (→)|Next (→)|||||
legacy.megabytes|{count} МБ|{count} MB|||||
legacy.kilobytes|{count} КБ|{count} KB|||||
legacy.objectSummary|Объектов: {count} · {tris} tris · |Objects: {count} · {tris} tris · |||||
legacy.modelCount|Моделей: {count}|Models: {count}|||||
legacy.renderCount|Рендер: {count}|Rendering: {count}|||||
legacy.renderMissingCount|Отрендерить недостающие ({count})|Render missing ({count})|||||
legacy.queuedCount|В очереди на рендер: {count}|Render queue: {count}|||||
legacy.materialCount|Материалы ({count})|Materials ({count})|||||
legacy.objectCount|Объекты ({count})|Objects ({count})|||||
legacy.objectCountOf|Объекты ({count} из {total})|Objects ({count} of {total})|||||
experimental.clipCount|{rig} · клипы {built}/{total}|{rig} · clips {built}/{total}|||||
experimental.faceCount| · Граней: {count}| · Faces: {count}|||||
experimental.sharedRig| — Риг {rig}, общий для всех персонажей| — Rig {rig}, shared by all characters|||||
experimental.frameCount|Кадров: {count}|Frames: {count}|||||
experimental.clipDuration|{clip} · {seconds} с|{clip} · {seconds} s|||||
experimental.clipAbsent|{clip} · нет|{clip} · missing|||||
experimental.templateLabel|Шаблон {name} (A-поза, humanoid_v1)|Template {name} (A-pose, humanoid_v1)|||||
experimental.solid|Поверхность|Solid|||||
experimental.wireframe|Каркас|Wireframe|||||
experimental.solidwire|Поверхность + каркас|Solid + wireframe|||||
experimental.normals|Нормали|Normals|||||
experimental.armature|Скелет|Armature|||||
experimental.weights|Веса|Weights|||||
experimental.meshBounds|Габарит: {size} м (X · Y↑ · Z)|Bounds: {size} m (X · Y↑ · Z)|||||
experimental.meshMaterials|Материалы: {names}|Materials: {names}|||||
experimental.meshRig|Скелет: да · костей {bones} · групп с весом {groups} · до {max} костей на вершину|Armature: yes · bones {bones} · weighted groups {groups} · up to {max} bones per vertex|||||
experimental.analysisCounts|Объектов: {objects} · мешей: {meshes} · материалов: {materials}|Objects: {objects} · meshes: {meshes} · materials: {materials}|||||
experimental.fileBounds|Размер: {size} (единицы файла)|Size: {size} (file units)|||||
experimental.uvGroups| · UV {uv} · групп {groups} · нормали: | · UV {uv} · groups {groups} · normals: |||||
experimental.boundaryEdges| · Открытых рёбер: {count}| · Boundary edges: {count}|||||
experimental.modifierList| · Модификаторы: {names}| · Modifiers: {names}|||||
experimental.normalization|Нормализация: ×{scale}, поворот {turn}°, рост {height} м, стопы на z = 0, лицо −Y (glTF +Z)|Normalization: ×{scale}, turn {turn}°, height {height} m, feet at z = 0, facing −Y (glTF +Z)|||||
experimental.licenseValue|Лицензия: {name}|License: {name}|||||
experimental.authorValue|Автор: {name}|Author: {name}|||||
experimental.landmarkCount|Ориентиров: {count} · до {max} костей на вершину|Landmarks: {count} · up to {max} bones per vertex|||||
experimental.poseValue| · Поза {name}| · Pose {name}|||||
experimental.templateStats|{vertices} v · {faces} f · {tris} tris · ≤{max} костей/вершину|{vertices} v · {faces} f · {tris} tris · ≤{max} bones/vertex|||||
experimental.repairCounts|Ремонт: сварено {welded}, закрыто дыр {filled}, нормали {normals}|Repair: welded {welded}, holes filled {filled}, normals {normals}|||||
experimental.supportLoops|Опорные петли: {names}|Support loops: {names}|||||
experimental.templateSource|Из {source} · {tris} tris|From {source} · {tris} tris|||||
pack.zkChassis|Zuk · шасси|Zuk · chassis|Zuk · chasis|Zuk · chassi|Zuk · 底盘|Zuk · châssis|Zuk · Fahrgestell
pack.zkCab|Zuk · кабина|Zuk · cab|Zuk · cabina|Zuk · cabine|Zuk · 驾驶室|Zuk · cabine|Zuk · Fahrerhaus
pack.zkBody|Zuk · грузовой кузов|Zuk · cargo body|Zuk · carrocería de carga|Zuk · carroceria de carga|Zuk · 货厢|Zuk · caisse de chargement|Zuk · Laderaum
pack.zkAxle|Zuk · ось и подвеска|Zuk · axle and suspension|Zuk · eje y suspensión|Zuk · eixo e suspensão|Zuk · 车轴与悬架|Zuk · essieu et suspension|Zuk · Achse und Federung
pack.zkWheel|Zuk · колесо|Zuk · wheel|Zuk · rueda|Zuk · roda|Zuk · 车轮|Zuk · roue|Zuk · Rad
pack.zkLamp|Zuk · фонарь|Zuk · lamp|Zuk · faro|Zuk · farol|Zuk · 车灯|Zuk · feu|Zuk · Leuchte
pack.zkMaterials|Zuk · образцы материалов|Zuk · material samples|Zuk · muestras de materiales|Zuk · amostras de materiais|Zuk · 材质样本|Zuk · échantillons de matériaux|Zuk · Materialmuster
pack.mtChassis|Грузовик · шасси|Truck · chassis|Camión · chasis|Caminhão · chassi|卡车 · 底盘|Camion · châssis|Lkw · Fahrgestell
pack.mtCabin|Грузовик · кабина|Truck · cab|Camión · cabina|Caminhão · cabine|卡车 · 驾驶室|Camion · cabine|Lkw · Fahrerhaus
pack.mtCargoBox|Грузовик · фургон|Truck · cargo box|Camión · caja de carga|Caminhão · baú de carga|卡车 · 货厢|Camion · caisse de chargement|Lkw · Kofferaufbau
pack.mtWheelset|Грузовик · колёсная ось|Truck · wheelset|Camión · eje de ruedas|Caminhão · eixo de rodas|卡车 · 轮对|Camion · essieu de roues|Lkw · Radsatz
pack.mtExhaust|Грузовик · выхлоп|Truck · exhaust|Camión · escape|Caminhão · escapamento|卡车 · 排气管|Camion · échappement|Lkw · Auspuff
pack.mtTank|Грузовик · топливный бак|Truck · fuel tank|Camión · depósito de combustible|Caminhão · tanque de combustível|卡车 · 油箱|Camion · réservoir|Lkw · Kraftstofftank
pack.mtToolbox|Грузовик · инструментальный ящик|Truck · toolbox|Camión · caja de herramientas|Caminhão · caixa de ferramentas|卡车 · 工具箱|Camion · boîte à outils|Lkw · Werkzeugkasten
pack.tdBase|TD · основание|TD · base|TD · base|TD · base|TD · 底座|TD · base|TD · Basis
pack.tdBody|TD · корпус|TD · body|TD · cuerpo|TD · corpo|TD · 主体|TD · corps|TD · Körper
pack.tdBarrel|TD · ствол|TD · barrel|TD · cañón|TD · cano|TD · 炮管|TD · canon|TD · Rohr
pack.tdLauncher|TD · ракетная установка|TD · missile launcher|TD · lanzamisiles|TD · lançador de mísseis|TD · 导弹发射器|TD · lance-missiles|TD · Raketenwerfer
pack.tdLeg|TD · механическая нога|TD · mechanical leg|TD · pata mecánica|TD · perna mecânica|TD · 机械腿|TD · patte mécanique|TD · Mechanisches Bein
pack.tdLight|TD · световой акцент|TD · accent light|TD · luz de acento|TD · luz de destaque|TD · 装饰灯|TD · éclairage d’accent|TD · Akzentlicht
pack.tdPanel|TD · панель|TD · panel|TD · panel|TD · painel|TD · 面板|TD · panneau|TD · Platte
pack.tdPedestal|TD · пьедестал|TD · pedestal|TD · pedestal|TD · pedestal|TD · 基座|TD · piédestal|TD · Sockel
pack.tdRing|TD · энергокольцо|TD · energy ring|TD · anillo de energía|TD · anel de energia|TD · 能量环|TD · anneau d’énergie|TD · Energiering
pack.tdSensor|TD · сенсор|TD · sensor|TD · sensor|TD · sensor|TD · 传感器|TD · capteur|TD · Sensor
pack.tdTowerBase|TD · базовая башня|TD · tower base|TD · torre base|TD · torre base|TD · 基础防御塔|TD · tour de base|TD · Basisturm
pack.tdEnemyBase|TD · базовый враг|TD · enemy base|TD · enemigo base|TD · inimigo base|TD · 基础敌人|TD · ennemi de base|TD · Basisgegner
pack.tdWalkerBase|TD · базовый шагающий враг|TD · walker base|TD · caminante base|TD · inimigo caminhante base|TD · 基础步行敌人|TD · marcheur de base|TD · Basisläufer
pack.evolutionPlinth|Подиум эволюции|Evolution plinth|Podio de evolución|Base de evolução|演化展示台|Socle d’évolution|Entwicklungspodest
`.trim();

export type TranslationRow = readonly [string, string, string?, string?, string?, string?, string?];
export const messages: Record<string, TranslationRow> = Object.fromEntries(rows.split("\n").map((line) => {
  const [key, ...values] = line.split("|");
  if (!key || values.length !== LOCALES.length) throw new Error(`Invalid translation row: ${key}`);
  return [key, values as unknown as TranslationRow];
}));
export type MessageKey =
    "nav.components"
  | "nav.assets"
  | "nav.materials"
  | "nav.characters"
  | "nav.sections"
  | "nav.language"
  | "nav.guide"
  | "nav.theme"
  | "nav.themeHint"
  | "nav.skip"
  | "nav.backRegistry"
  | "common.loading"
  | "common.retry"
  | "common.reload"
  | "common.close"
  | "common.closeDialog"
  | "common.cancel"
  | "common.save"
  | "common.saving"
  | "common.add"
  | "common.remove"
  | "common.refresh"
  | "common.reset"
  | "common.all"
  | "common.any"
  | "common.yes"
  | "common.no"
  | "common.empty"
  | "common.description"
  | "common.name"
  | "common.level"
  | "common.note"
  | "common.tags"
  | "common.ready"
  | "common.noChanges"
  | "common.nothingChanged"
  | "common.noPreview"
  | "common.noResults"
  | "common.default"
  | "common.up"
  | "common.down"
  | "common.show"
  | "common.hide"
  | "status.draft"
  | "status.built"
  | "status.failed"
  | "status.approved"
  | "status.archived"
  | "status.queued"
  | "status.running"
  | "build.events"
  | "build.connected"
  | "build.reconnecting"
  | "build.queue"
  | "build.build"
  | "build.rebuild"
  | "build.create"
  | "build.need"
  | "build.failure"
  | "build.recipeFailure"
  | "build.noModel"
  | "build.noBuiltModel"
  | "build.queued"
  | "build.rebuilding"
  | "build.sending"
  | "build.starting"
  | "build.never"
  | "build.invalid"
  | "build.successFirst"
  | "error.offline"
  | "error.page"
  | "error.route"
  | "error.server"
  | "error.number"
  | "catalog.view"
  | "catalog.reset"
  | "catalog.searchPlaceholder"
  | "catalog.search"
  | "catalog.group"
  | "catalog.ungrouped"
  | "catalog.list"
  | "catalog.cards"
  | "catalog.collapseTags"
  | "catalog.matchAll"
  | "catalog.empty"
  | "catalog.tryFilters"
  | "catalog.type"
  | "catalog.preview"
  | "catalog.priority"
  | "catalog.addAsset"
  | "catalog.manageGroups"
  | "catalog.table"
  | "tags.title"
  | "tags.search"
  | "tags.searchLabel"
  | "tags.manage"
  | "tags.input"
  | "tags.newName"
  | "tags.name"
  | "tags.delete"
  | "tags.deleting"
  | "tags.deleteAll"
  | "tags.saveAll"
  | "tags.noTags"
  | "tags.notFound"
  | "entity.variants"
  | "entity.noVariants"
  | "entity.selectVariant"
  | "entity.loadingVariant"
  | "entity.branch"
  | "entity.approve"
  | "entity.unapprove"
  | "entity.archive"
  | "entity.unarchive"
  | "entity.edit"
  | "entity.compose"
  | "entity.params"
  | "entity.slots"
  | "entity.sockets"
  | "entity.build"
  | "entity.body"
  | "entity.structure"
  | "entity.part"
  | "entity.noInheritance"
  | "entity.rating"
  | "entity.noRating"
  | "entity.removeRating"
  | "entity.other"
  | "entity.changedHint"
  | "entity.onlyDifferences"
  | "entity.parameter"
  | "branch.parentValue"
  | "branch.note"
  | "branch.newNote"
  | "branch.save"
  | "branch.changed"
  | "compose.params"
  | "compose.select"
  | "compose.empty"
  | "compose.body"
  | "compose.newRoot"
  | "compose.parent"
  | "compose.note"
  | "compose.noCompatible"
  | "compose.help"
  | "compose.deltaHelp"
  | "create.title"
  | "create.assetName"
  | "create.description"
  | "create.firstVariant"
  | "create.chooseVariant"
  | "create.base"
  | "create.removeSlot"
  | "create.readyModel"
  | "create.slotName"
  | "create.attachment"
  | "create.chooseSocket"
  | "create.offset"
  | "create.origin"
  | "create.noSocket"
  | "create.invalidId"
  | "create.needName"
  | "create.needBody"
  | "create.gridError"
  | "create.composition"
  | "create.addPart"
  | "create.bounds"
  | "create.grid"
  | "create.tags"
  | "create.variantNote"
  | "viewer.iso"
  | "viewer.front"
  | "viewer.back"
  | "viewer.right"
  | "viewer.left"
  | "viewer.top"
  | "viewer.bottom"
  | "viewer.side"
  | "viewer.pose"
  | "viewer.autoRotate"
  | "viewer.wireframe"
  | "viewer.bounds"
  | "viewer.sockets"
  | "viewer.collision"
  | "viewer.skeleton"
  | "viewer.reset"
  | "viewer.replay"
  | "viewer.pause"
  | "viewer.play"
  | "viewer.clip"
  | "viewer.animation"
  | "viewer.aim"
  | "viewer.yaw"
  | "viewer.pitch"
  | "viewer.rotation"
  | "viewer.elevation"
  | "viewer.aimHelp"
  | "viewer.synced"
  | "material.bands"
  | "material.light"
  | "material.specular"
  | "material.rim"
  | "material.halftone"
  | "material.outline"
  | "material.description"
  | "material.presets"
  | "material.compareHint"
  | "material.loading"
  | "material.error"
  | "material.model"
  | "material.pbr"
  | "material.compare"
  | "material.closeCompare"
  | "material.renderQueued"
  | "material.notBuilt"
  | "material.blenderPreview"
  | "projections.title"
  | "projections.create"
  | "projections.section"
  | "projections.loading"
  | "projections.help"
  | "blockout.title"
  | "blockout.parts"
  | "blockout.loading"
  | "blockout.openBlender"
  | "blockout.download"
  | "blockout.preparing"
  | "edit.save"
  | "edit.revert"
  | "edit.back"
  | "edit.source"
  | "edit.position"
  | "edit.snap"
  | "edit.noSnap"
  | "edit.note"
  | "edit.selectSlot"
  | "edit.restore"
  | "edit.centerSocket"
  | "edit.centerBody"
  | "stats.polygons"
  | "stats.vertices"
  | "stats.boundsM"
  | "stats.boundsVox"
  | "stats.duration"
  | "stats.log"
  | "meta.blockout"
  | "meta.silhouette"
  | "meta.details"
  | "meta.complexity"
  | "meta.shader"
  | "meta.materialShader"
  | "meta.structureHint"
  | "meta.levelHint"
  | "meta.llm"
  | "pack.zukTruck"
  | "pack.modularTruck"
  | "pack.truckEvolution"
  | "pack.heliEvolution"
  | "pack.truck"
  | "pack.heli"
  | "pack.td"
  | "pack.toon"
  | "pack.gatling"
  | "pack.missile"
  | "pack.support"
  | "pack.scout"
  | "pack.grunt"
  | "pack.flyer"
  | "pack.cover"
  | "pack.path"
  | "param.stage"
  | "param.part"
  | "param.bodyColor"
  | "param.trimColor"
  | "param.color"
  | "param.height"
  | "param.width"
  | "param.length"
  | "param.depth"
  | "param.finish"
  | "param.roughness"
  | "param.metallic"
  | "param.bands"
  | "param.softness"
  | "param.shadowStrength"
  | "param.shadowColor"
  | "param.lightTint"
  | "param.outlineMode"
  | "param.outlineWidth"
  | "param.outlineColor"
  | "param.specularSize"
  | "param.rimWidth"
  | "param.rimColor"
  | "param.halftoneScale"
  | "material.liveHelp"
  | "material.previewHelp"
  | "material.pbrHint"
  | "material.exportHelp"
  | "viewer.materialHint"
  | "viewer.gridHint"
  | "viewer.showSockets"
  | "viewer.showCollision"
  | "viewer.showBones"
  | "viewer.webglLost"
  | "viewer.noParts"
  | "create.help"
  | "create.voxelHelp"
  | "entity.docResolved"
  | "entity.llmContext"
  | "entity.diffUnavailable"
  | "entity.sameArtifact"
  | "entity.root"
  | "entity.forkBlender"
  | "entity.openedBlender"
  | "entity.blenderAlready"
  | "entity.manualSlots"
  | "entity.manualParams"
  | "entity.blenderSaveHelp"
  | "entity.freeSockets"
  | "entity.socketInterface"
  | "entity.socketOccupied"
  | "entity.verified"
  | "entity.compositionVerified"
  | "edit.help"
  | "edit.dragHelp"
  | "edit.offsetHelp"
  | "edit.noneOccupied"
  | "edit.originalUnbuilt"
  | "edit.missingNodes"
  | "edit.choosePart"
  | "edit.noNode"
  | "edit.snapHint"
  | "edit.notePlaceholder"
  | "edit.leftRight"
  | "edit.downUp"
  | "edit.backForward"
  | "edit.backDirection"
  | "edit.forward"
  | "edit.center"
  | "core.asset"
  | "core.component"
  | "core.tagVariant"
  | "core.noTags"
  | "core.unavailablePreview"
  | "core.cast"
  | "core.castTogether"
  | "core.animations"
  | "core.clipMissing"
  | "core.sharedSkeleton"
  | "core.rig"
  | "core.noRig"
  | "core.modified"
  | "core.modifiedDot"
  | "core.newBreadcrumb"
  | "core.composeBreadcrumb"
  | "core.editBreadcrumb"
  | "core.variantMany"
  | "core.variantOne"
  | "core.variantFew"
  | "core.addTag"
  | "core.builtCheck"
  | "core.required"
  | "core.optional"
  | "tags.related"
  | "tags.registry"
  | "tags.unavailable"
  | "tags.loading"
  | "tags.reloadHelp"
  | "tags.loadingCards"
  | "tags.base"
  | "tags.structure"
  | "tags.unavailableRetry"
  | "tags.selectHelp"
  | "tags.noEntityTags"
  | "tags.relatedType"
  | "tags.noRelated"
  | "tags.onlySettings"
  | "catalog.importantLabel"
  | "catalog.otherLabel"
  | "catalog.tagsLabel"
  | "catalog.groupLabel"
  | "catalog.levelLabel"
  | "catalog.closeSettings"
  | "catalog.configureTags"
  | "catalog.tagSettingsUnavailable"
  | "catalog.closeGroups"
  | "catalog.groupsUnavailable"
  | "catalog.tagPlaceholder"
  | "catalog.addPriority"
  | "catalog.tagsSaved"
  | "catalog.settingsError"
  | "catalog.allSections"
  | "catalog.tagOrderHelp"
  | "catalog.moveUp"
  | "catalog.moveDown"
  | "catalog.emptyTagList"
  | "catalog.groupId"
  | "catalog.groupName"
  | "catalog.newGroupName"
  | "catalog.invalidGroupId"
  | "catalog.needGroupName"
  | "catalog.logicalGroups"
  | "catalog.orderOnly"
  | "catalog.groupHelp"
  | "catalog.emptyGroupName"
  | "catalog.addGroup"
  | "catalog.groupsSaved"
  | "catalog.groupsError"
  | "catalog.sectionError"
  | "catalog.managerError"
  | "catalog.staleError"
  | "catalog.otherTags"
  | "blockout.noGroup"
  | "blockout.intro"
  | "blockout.table"
  | "blockout.projections"
  | "blockout.breadcrumb"
  | "blockout.components"
  | "blockout.queueing"
  | "blockout.building"
  | "blockout.unavailable"
  | "blockout.snapshots"
  | "blockout.loadingParts"
  | "blockout.partsUnavailable"
  | "blockout.assetsLabel"
  | "blockout.noVariant"
  | "blockout.empty"
  | "blockout.retry"
  | "blockout.views"
  | "blockout.noModels"
  | "blockout.error"
  | "blockout.actionError"
  | "blockout.alreadyOpen"
  | "blockout.prepared"
  | "edit.quarterVoxel"
  | "edit.tenth"
  | "edit.half"
  | "tags.changeHelp"
  | "tags.mergeHelp"
  | "tags.refreshError"
  | "tags.catalogRefreshError"
  | "error.oldApi"
  | "blockout.chooseAssetHelp"
  | "blockout.buildFirst"
  | "blockout.viewHelp"
  | "blockout.retryParts"
  | "blockout.queuedNotice"
  | "blockout.allBuilt"
  | "blockout.readyNotice"
  | "blockout.openNotice"
  | "blockout.groupHint"
  | "blockout.loadingLink"
  | "projections.tooltip"
  | "blender.forkAssetHelp"
  | "blender.forkComponentHelp"
  | "catalog.abstractBases"
  | "common.retryAction"
  | "dynamic.created"
  | "dynamic.compare"
  | "dynamic.diff"
  | "dynamic.chain"
  | "dynamic.inheritance"
  | "dynamic.mounts"
  | "dynamic.from"
  | "dynamic.branchTitle"
  | "dynamic.parentHelp"
  | "dynamic.catalogCount"
  | "dynamic.moreTags"
  | "dynamic.items"
  | "dynamic.groupExists"
  | "dynamic.groupName"
  | "dynamic.deleteGroup"
  | "dynamic.composeTitle"
  | "dynamic.socket"
  | "dynamic.bodySocket"
  | "dynamic.accepts"
  | "dynamic.previous"
  | "dynamic.incompatible"
  | "dynamic.slotVariant"
  | "dynamic.partNumber"
  | "dynamic.attachment"
  | "dynamic.slotInvalidName"
  | "dynamic.slotDuplicate"
  | "dynamic.slotChoose"
  | "dynamic.slotChooseSocket"
  | "dynamic.slotIncompatible"
  | "dynamic.slotOffset"
  | "dynamic.preview"
  | "dynamic.changedFields"
  | "dynamic.savedMaterial"
  | "dynamic.blenderRender"
  | "dynamic.glbError"
  | "dynamic.openPng"
  | "dynamic.rating"
  | "dynamic.setRating"
  | "dynamic.buildState"
  | "dynamic.editTitle"
  | "dynamic.offsetRange"
  | "dynamic.changedSlots"
  | "dynamic.host"
  | "dynamic.meters"
  | "dynamic.sheetTitle"
  | "dynamic.sheetAsset"
  | "dynamic.buildParts"
  | "dynamic.readyParts"
  | "dynamic.queueSuffix"
  | "dynamic.partReuse"
  | "dynamic.tagCount"
  | "dynamic.deleteTag"
  | "dynamic.blendPreparing"
  | "dynamic.blendOpen"
  | "dynamic.blendAlready"
  | "dynamic.blendError"
  | "dynamic.rebuild"
  | "dynamic.cannotBuild"
  | "dynamic.buildFailed"
  | "dynamic.tableHint"
  | "dynamic.sheetLink"
  | "dynamic.blendContinue"
  | "dynamic.manualGeometry"
  | "dynamic.treeHint"
  | "dynamic.structure"
  | "dynamic.relationships"
  | "dynamic.primaryMass"
  | "dynamic.secondary"
  | "dynamic.density"
  | "dynamic.slotParams"
  | "dynamic.sheetBlenderHelp"
  | "dynamic.sheetQueueError"
  | "dynamic.sheetOpenError"
  | "dynamic.noEditVariant"
  | "dynamic.placementSuffix"
  | "dynamic.plainSocket"
  | "dynamic.tagRelations"
  | "dynamic.tagRemovalHelp"
  | "dynamic.tagRemoved"
  | "dynamic.tagRenamed"
  | "dynamic.tagsUpdated"
  | "experimental.proportions"
  | "experimental.head"
  | "experimental.hair"
  | "experimental.outfit"
  | "experimental.palette"
  | "experimental.onlyLeft"
  | "experimental.sideBySide"
  | "experimental.overlay"
  | "experimental.wires"
  | "experimental.visualReference"
  | "experimental.topology"
  | "experimental.derivative"
  | "experimental.productionTemplate"
  | "experimental.noReferences"
  | "experimental.normalized"
  | "experimental.regions"
  | "experimental.bone"
  | "experimental.opacityHint"
  | "experimental.noCompare"
  | "experimental.isolate"
  | "experimental.frame"
  | "experimental.meshes"
  | "experimental.showAll"
  | "experimental.mesh"
  | "experimental.glbCounts"
  | "experimental.leftSuffix"
  | "experimental.rightSuffix"
  | "experimental.noArmature"
  | "experimental.vertexColors"
  | "experimental.noVertexColors"
  | "experimental.sourceAnalysis"
  | "experimental.noAnalysis"
  | "experimental.rights"
  | "experimental.unspecified"
  | "experimental.rightsHelp"
  | "experimental.semantics"
  | "experimental.noSemantics"
  | "experimental.templatesFromReference"
  | "experimental.noTemplates"
  | "experimental.referenceHelp"
  | "experimental.references"
  | "experimental.templates"
  | "experimental.opacity"
  | "experimental.sceneHelp"
  | "experimental.weightsHelp"
  | "experimental.catalogHint"
  | "experimental.castBreadcrumb"
  | "experimental.castSource"
  | "experimental.castMissing"
  | "experimental.castSkipped"
  | "legacy.hint"
  | "legacy.rendering"
  | "legacy.animatedHint"
  | "legacy.search"
  | "legacy.sources"
  | "legacy.formatsAll"
  | "legacy.animated"
  | "legacy.root"
  | "legacy.help"
  | "legacy.render"
  | "legacy.rerender"
  | "legacy.copyPath"
  | "legacy.path"
  | "legacy.file"
  | "legacy.formats"
  | "legacy.renderFrom"
  | "legacy.size"
  | "legacy.modified"
  | "legacy.version"
  | "legacy.scene"
  | "legacy.geometry"
  | "legacy.objects"
  | "legacy.preview"
  | "legacy.openError"
  | "legacy.notRendered"
  | "legacy.pathCopied"
  | "legacy.previous"
  | "legacy.next"
  | "legacy.megabytes"
  | "legacy.kilobytes"
  | "legacy.objectSummary"
  | "legacy.modelCount"
  | "legacy.renderCount"
  | "legacy.renderMissingCount"
  | "legacy.queuedCount"
  | "legacy.materialCount"
  | "legacy.objectCount"
  | "legacy.objectCountOf"
  | "experimental.clipCount"
  | "experimental.faceCount"
  | "experimental.sharedRig"
  | "experimental.frameCount"
  | "experimental.clipDuration"
  | "experimental.clipAbsent"
  | "experimental.templateLabel"
  | "experimental.solid"
  | "experimental.wireframe"
  | "experimental.solidwire"
  | "experimental.normals"
  | "experimental.armature"
  | "experimental.weights"
  | "experimental.meshBounds"
  | "experimental.meshMaterials"
  | "experimental.meshRig"
  | "experimental.analysisCounts"
  | "experimental.fileBounds"
  | "experimental.uvGroups"
  | "experimental.boundaryEdges"
  | "experimental.modifierList"
  | "experimental.normalization"
  | "experimental.licenseValue"
  | "experimental.authorValue"
  | "experimental.landmarkCount"
  | "experimental.poseValue"
  | "experimental.templateStats"
  | "experimental.repairCounts"
  | "experimental.supportLoops"
  | "experimental.templateSource"
  | "pack.zkChassis"
  | "pack.zkCab"
  | "pack.zkBody"
  | "pack.zkAxle"
  | "pack.zkWheel"
  | "pack.zkLamp"
  | "pack.zkMaterials"
  | "pack.mtChassis"
  | "pack.mtCabin"
  | "pack.mtCargoBox"
  | "pack.mtWheelset"
  | "pack.mtExhaust"
  | "pack.mtTank"
  | "pack.mtToolbox"
  | "pack.tdBase"
  | "pack.tdBody"
  | "pack.tdBarrel"
  | "pack.tdLauncher"
  | "pack.tdLeg"
  | "pack.tdLight"
  | "pack.tdPanel"
  | "pack.tdPedestal"
  | "pack.tdRing"
  | "pack.tdSensor"
  | "pack.tdTowerBase"
  | "pack.tdEnemyBase"
  | "pack.tdWalkerBase"
  | "pack.evolutionPlinth";
