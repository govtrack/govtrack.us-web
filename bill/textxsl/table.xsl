<?xml version='1.0'?>
<!--  ===========================================================  -->
<!--  MODULE:    Table XSL for Legislative Branch Bills  XSLT      -->
<!--  VERSION:   1.9/Table Companion for billres.xsl 1.9           -->
<!--  DATE:      February 8, 2008                                  -->
<!--  Previous version and date:                 -->
<!-- =============================================================
	Formal Public Identifier:
	Table.xsl                                                    -->
	<!--  SYSTEM:    Legislative Branch XSL                            -->
	<!--  PURPOSE:   Contains specific information for display of      -->
	<!--             tables in Bills and Resolutions on the web        -->
	<!--                                                               -->
	<!--  CONTAINS:  1) Calls to res.dtd and bill.dtd                  -->
	<!--             2) Overall structure of a Bill, Resolution,       -->
	<!--                Amendments                                     -->
	<!--                                                               -->
	<!--  MODULES REQUIRED:                                            -->
	<!--             XSL and DTD Common Elements                       -->
	<!--                                                               -->
	<!--  CREATED FOR:                                                 -->
	<!--             House of Representatives, Senate and The Library  -->
	<!--             of Congress                                       -->
	<!--  ORIGINAL CREATION DATE:                                      -->
	<!--            February 6,  2004                                  -->
	<!--  DEVELOPED BY: DataStream/Government Printing Office          -->
	<!--  DEVELOPER: Alia Malhas/Tanya Braginsky                       -->
	<!--  SEND COMMENTS/QUERIES TO: Kathleen Swiatek(kswiatek@gpo.gov) -->
	<!-- ============================================================= -->
	<!--                    CHANGE HISTORY -->
	
	<!--  Changes incorporated within 1.9 (February 8, 2008) as well
		as previous changes:
		1. Adjusted to allow for tables as created by the new table
		tool 
		Previos changes:
		1. Allowed leader dots display, grayed out the borders,
		removed horizontal and vertical rules
		2. Fixed alignment in last column
		3. Adjustment for table width                                -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
	<!-- blank lines before/after template -->
	<xsl:template name="BlankLine">
		<xsl:param name="cnt"/>
		<xsl:choose>
			<xsl:when test="$cnt='0'"> </xsl:when>
			<xsl:when test="$cnt='1'">
				<br/>
			</xsl:when>
			<xsl:when test="$cnt='2'">
				<br/>
				<br/>
			</xsl:when>
			<xsl:when test="$cnt='3'">
				<br/>
				<br/>
				<br/>
			</xsl:when>
			<xsl:when test="$cnt='4'">
				<br/>
				<br/>
				<br/>
				<br/>
			</xsl:when>
			<xsl:when test="$cnt='5'">
				<br/>
				<br/>
				<br/>
				<br/>
				<br/>
			</xsl:when>
			<xsl:when test="$cnt='6'">
				<br/>
				<br/>
				<br/>
				<br/>
				<br/>
				<br/>
			</xsl:when>
			<xsl:when test="$cnt='7'">
				<br/>
				<br/>
				<br/>
				<br/>
				<br/>
				<br/>
				<br/>
			</xsl:when>
		</xsl:choose>
	</xsl:template>
	<!-- Indent template -->
	<xsl:template name="Indent">
		<xsl:param name="num"/>
		<xsl:choose>
			<xsl:when test="$num=2">
				<xsl:text>&#160;&#160;</xsl:text>
			</xsl:when>
			<xsl:when test="$num=4">
				<xsl:text>&#160;&#160;&#160;&#160;</xsl:text>
			</xsl:when>
			<xsl:when test="$num=6">
				<xsl:text>&#160;&#160;&#160;&#160;&#160;&#160;</xsl:text>
			</xsl:when>
			<xsl:when test="$num=8">
				<xsl:text>&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;</xsl:text>
			</xsl:when>
			<xsl:when test="$num=10">
				<xsl:text>&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;</xsl:text>
			</xsl:when>
			<xsl:when test="$num=12">
				<xsl:text>&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;</xsl:text>
			</xsl:when>
			<xsl:when test="$num=14">
				<xsl:text>&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;</xsl:text>
			</xsl:when>
			<xsl:when test="$num=16">
				<xsl:text>&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;</xsl:text>
			</xsl:when>
			<xsl:otherwise>
				<xsl:text/>
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	<!-- border template -->
	<xsl:template name="border">
		<xsl:param name="side" select="'left'"/>
		<xsl:param name="padding" select="0"/>
		<xsl:param name="style" select="'solid'"/>
		<xsl:param name="color" select="'#FFFFFF'"/>
		<xsl:param name="thickness" select="1"/>
		<!-- Note: Some browsers (mozilla) require at least a width and style. -->
		<xsl:choose>
			<xsl:when
				test="($thickness != ''
                     and $style != ''
                     and $color != '')
                    or ($thickness != ''
                        and $style != '')
                    or ($thickness != '')">
				<!-- use the compound property if we can: -->
				<!-- it saves space and probably works more reliably -->
				<xsl:text>border-</xsl:text>
				<xsl:value-of select="$side"/>
				<xsl:text>: </xsl:text>
				<xsl:value-of select="$thickness"/>
				<xsl:text> </xsl:text>
				<xsl:value-of select="$style"/>
				<xsl:text> </xsl:text>
				<xsl:value-of select="$color"/>
				<xsl:text>; </xsl:text>
			</xsl:when>
			<xsl:otherwise>
				<!-- we need to specify the styles individually -->
				<xsl:if test="$thickness != ''">
					<xsl:text>border-</xsl:text>
					<xsl:value-of select="$side"/>
					<xsl:text>-width: </xsl:text>
					<xsl:value-of select="$thickness"/>
					<xsl:text>; </xsl:text>
				</xsl:if>
				<xsl:if test="$style != ''">
					<xsl:text>border-</xsl:text>
					<xsl:value-of select="$side"/>
					<xsl:text>-style: </xsl:text>
					<xsl:value-of select="$style"/>
					<xsl:text>; </xsl:text>
				</xsl:if>
				<xsl:if test="$color != ''">
					<xsl:text>border-</xsl:text>
					<xsl:value-of select="$side"/>
					<xsl:text>-color: </xsl:text>
					<xsl:value-of select="$color"/>
					<xsl:text>; </xsl:text>
				</xsl:if>
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>

	<!-- column seperator template -->
	<xsl:template name="ColSep">
		<xsl:param name="color"/>
		<xsl:param name="style"/>
		<xsl:param name="ruleweight"/>
		<xsl:if test="$style='double'">
			<xsl:call-template name="border">
				<xsl:with-param name="side" select="'right'"/>
				<xsl:with-param name="style" select="$style"/>
				<xsl:with-param name="color" select="$color"/>
				<xsl:with-param name="thickness" select="'thick'"/>
			</xsl:call-template>
		</xsl:if>
		<xsl:if test="not($style='double')">
			<xsl:if
				test="number(substring-before(substring-after(substring-after(substring-after(substring-after($ruleweight, '.'), '.'), '.'),'.'),'.'))  =0">
				<xsl:call-template name="border">
					<xsl:with-param name="side" select="'right'"/>
					<xsl:with-param name="style" select="$style"/>
					<xsl:with-param name="color" select="'#FFFFFF'"/>
					<xsl:with-param name="thickness">
						<xsl:value-of select="'0'"/>
					</xsl:with-param>
				</xsl:call-template>
			</xsl:if>
			<xsl:if
				test="number(substring-before(substring-after(substring-after(substring-after(substring-after($ruleweight, '.'), '.'), '.'),'.'),'.'))  &gt; 0">
				<xsl:call-template name="border">
					<xsl:with-param name="side" select="'right'"/>
					<xsl:with-param name="style" select="$style"/>
					<xsl:with-param name="color" select="$color"/>
					<xsl:with-param name="thickness">
						<xsl:value-of
							select="number(substring-before(substring-after(substring-after(substring-after(substring-after($ruleweight, '.'), '.'), '.'),'.'),'.')) div 2"
						/>px </xsl:with-param>
				</xsl:call-template>
			</xsl:if>
		</xsl:if>
	</xsl:template>

	<!-- row seperator template -->
	<xsl:template name="RowSep">
		<xsl:param name="color"/>
		<xsl:param name="style"/>
		<xsl:param name="ruleweight"/>
		<xsl:if test="$style='double'">
			<xsl:call-template name="border">
				<xsl:with-param name="side" select="'bottom'"/>
				<xsl:with-param name="style" select="$style"/>
				<xsl:with-param name="color" select="$color"/>
				<xsl:with-param name="thickness" select="'thick'"/>
			</xsl:call-template>
		</xsl:if>
		<xsl:if test="not($style='double')">
			<xsl:if
				test="number(substring-before(substring-after(substring-after(substring-after($ruleweight, '.'), '.'),'.'),'.'))  = 0 ">
				<xsl:call-template name="border">
					<xsl:with-param name="side" select="'bottom'"/>
					<xsl:with-param name="style" select="$style"/>
					<xsl:with-param name="color" select="'#FFFFFF'"/>
					<xsl:with-param name="thickness">
						<xsl:value-of select="'0'"/>
					</xsl:with-param>
				</xsl:call-template>
			</xsl:if>
			<xsl:if
				test="number(substring-before(substring-after(substring-after(substring-after($ruleweight, '.'), '.'),'.'),'.'))  &gt; 0">
				<xsl:call-template name="border">
					<xsl:with-param name="side" select="'bottom'"/>
					<xsl:with-param name="style" select="$style"/>
					<xsl:with-param name="color" select="$color"/>
					<xsl:with-param name="thickness">
						<xsl:value-of
							select="number(substring-before(substring-after(substring-after(substring-after($ruleweight, '.'), '.'),'.'),'.')) div 2"
						/>px </xsl:with-param>
				</xsl:call-template>
			</xsl:if>
		</xsl:if>
	</xsl:template>

	<!-- side template -->
	<xsl:template name="BorderSides">
		<xsl:param name="color"/>
		<xsl:param name="ruleweight"/>
		<xsl:if test="number(substring-before($ruleweight, '.')) = 0 ">
			<xsl:call-template name="border">
				<xsl:with-param name="side" select="'left'"/>
				<xsl:with-param name="color" select="'#C0C0C0'"/>
			</xsl:call-template>
			<xsl:call-template name="border">
				<xsl:with-param name="side" select="'right'"/>
				<xsl:with-param name="color" select="'#C0C0C0'"/>
			</xsl:call-template>
		</xsl:if>
		<xsl:if test="number(substring-before($ruleweight, '.')) &gt; 0 ">
			<xsl:call-template name="border">
				<xsl:with-param name="side" select="'left'"/>
				<xsl:with-param name="color" select="$color"/>
				<xsl:with-param name="thickness">
					<xsl:value-of select="number(substring-before($ruleweight, '.')) div 2"/>px
				</xsl:with-param>
			</xsl:call-template>
			<xsl:call-template name="border">
				<xsl:with-param name="side" select="'right'"/>
				<xsl:with-param name="color" select="$color"/>
				<xsl:with-param name="thickness">
					<xsl:value-of select="number(substring-before($ruleweight, '.')) div 2"/>px
				</xsl:with-param>
			</xsl:call-template>
		</xsl:if>
	</xsl:template>

	<xsl:template name="Getleveldiff">
		<xsl:param name="pnd1"/>
		<xsl:param name="pnd2"/>
		<xsl:variable name="tmp1">
			<xsl:call-template name="LevelNumber">
				<xsl:with-param name="level" select="$pnd1"/>
			</xsl:call-template>
		</xsl:variable>
		<xsl:variable name="tmp2">
			<xsl:call-template name="LevelNumber">
				<xsl:with-param name="level" select="$pnd2"/>
			</xsl:call-template>
		</xsl:variable>
		<xsl:value-of select="$tmp1 - $tmp2"/>
	</xsl:template>

	<xsl:template name="LevelNumber">
		<xsl:param name="level"/>
		<xsl:choose>
			<xsl:when test="$level='section'">
				<xsl:value-of select="number(8)"/>
			</xsl:when>
			<xsl:when test="$level='subsection'">
				<xsl:value-of select="number(7)"/>
			</xsl:when>
			<xsl:when test="$level='paragraph'">
				<xsl:value-of select="number(6)"/>
			</xsl:when>
			<xsl:when test="$level='subparagraph'">
				<xsl:value-of select="number(5)"/>
			</xsl:when>
			<xsl:when test="$level='clause'">
				<xsl:value-of select="number(4)"/>
			</xsl:when>
			<xsl:when test="$level='subclause'">
				<xsl:value-of select="number(3)"/>
			</xsl:when>
			<xsl:when test="$level='item'">
				<xsl:value-of select="number(2)"/>
			</xsl:when>
			<xsl:when test="$level='subitem'">
				<xsl:value-of select="number(1)"/>
			</xsl:when>
			<xsl:when test="$level='table'">
				<xsl:value-of select="number(9)"/>
			</xsl:when>
			<xsl:when test="$level='quoted-block'">
				<xsl:value-of select="number(9)"/>
			</xsl:when>
		</xsl:choose>
	</xsl:template>
	<!-- end of templates -->

	<xsl:decimal-format NaN="0"/>

	<!-- table -->
	<xsl:template match="table">
		<xsl:variable name="isFormulaTable">
			<xsl:choose>
				<xsl:when test="contains(@table-template-name, 'formula') or contains(@table-template-name, 'Formula')">
					<xsl:text>true</xsl:text>
				</xsl:when>
				<xsl:otherwise>false</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:if test="not(name(preceding-sibling::*[1])='table')">
			<br/>
		</xsl:if>
		<xsl:if test="@blank-lines-before">
			<xsl:call-template name="BlankLine">
				<xsl:with-param name="cnt" select="./@blank-lines-before"/>
			</xsl:call-template>
		</xsl:if>
		<div id="left" align="center">
			<xsl:variable name="NegativeIndent">
				<xsl:choose>
					<xsl:when test="ancestor::subitem">
						<xsl:value-of select="6"/>
					</xsl:when>
					<xsl:when test="ancestor::item">
						<xsl:value-of select="6"/>
					</xsl:when>
					<xsl:when test="ancestor::subclause">
						<xsl:value-of select="6"/>
					</xsl:when>
					<xsl:when test="ancestor::clause">
						<xsl:value-of select="6"/>
					</xsl:when>
					<xsl:when test="ancestor::subparagraph">
						<xsl:value-of select="4"/>
					</xsl:when>
					<xsl:when test="ancestor::paragraph">
						<xsl:value-of select="2"/>
					</xsl:when>
					<xsl:when test="ancestor::subsection">
						<xsl:value-of select="2"/>
					</xsl:when>
				</xsl:choose>
			</xsl:variable>
			<xsl:variable name="NegativeIndent1">
				<xsl:if test="ancestor::quoted-block/@style='traditional'">
					<xsl:value-of select="2"/>
				</xsl:if>
				<xsl:if test="not(ancestor::quoted-block/@style='traditional')">
					<xsl:value-of select="2"/>
				</xsl:if>
			</xsl:variable>
			<!-- TB 30-Jan-2008 Tables on the web improvements -->
			<!-- According to new Table Tool - align-to -level attribute is not in use -->
			<!-- in case if it will be returned, we will be able to uncomment the code -->
			<!--xsl:variable name="NegativeIndent2">
				<xsl:choose>
					<xsl:when test="@align-to-level='subitem'">
						<xsl:value-of select="12"/>
					</xsl:when>
					<xsl:when test="@align-to-level='item'">
						<xsl:value-of select="10"/>
					</xsl:when>
					<xsl:when test="@align-to-level='subclause'">
						<xsl:value-of select="8"/>
					</xsl:when>
					<xsl:when test="@align-to-level='clause'">
						<xsl:value-of select="6"/>
					</xsl:when>
					<xsl:when test="@align-to-level='subparagraph'">
						<xsl:value-of select="4"/>
					</xsl:when>
					<xsl:when test="@align-to-level='paragraph'">
						<xsl:value-of select="2"/>
					</xsl:when>
					<xsl:when test="@align-to-level='subsection'">
						<xsl:value-of select="0"/>
					</xsl:when>
					<xsl:otherwise>
						<xsl:value-of select="0"/>
					</xsl:otherwise>
				</xsl:choose>
			</xsl:variable-->
			<xsl:attribute name="style">
				<xsl:if test="./tgroup/@offset-from-left">
					<xsl:text>margin-left: </xsl:text>
					<xsl:value-of select="./tgroup/@offset-from-left"/>
					<xsl:text>px; </xsl:text>
				</xsl:if>
				<xsl:if test="not(./tgroup/@offset-from-left)">
					<xsl:text>margin-left:</xsl:text>
					<!-- TB 30-Jan-2008 Tables on the web improvements - changed to be + -->
					<xsl:value-of select="0 + $NegativeIndent - $NegativeIndent1"/>
					<xsl:text>em; </xsl:text>
				</xsl:if>
			</xsl:attribute>
			<table cellpadding="0" cellspacing="0">
				<!-- TB 29Dec2008 adjust table width bug #884 -->
				<xsl:choose>
					<!-- TB May2009 Adjustment for the formula tables -->					
					<xsl:when test="$isFormulaTable='true'">
						<xsl:variable name="tableWidth">
							<xsl:call-template name="calcFormulaTableWidth"/>	
						</xsl:variable>
						<!--was printing for testing purpose only xsl:value-of select="$tableWidth"/-->
						<xsl:choose>
							<xsl:when test="number($tableWidth) &lt; 30">
								<xsl:attribute name="width">
									<xsl:text>20%</xsl:text>
								</xsl:attribute>
							</xsl:when>
							<xsl:when test="number($tableWidth) >= 30 and number($tableWidth) &lt; 50 " >
								<xsl:attribute name="width">
									<xsl:text>35%</xsl:text>
								</xsl:attribute>
							</xsl:when>
							<xsl:when test="number($tableWidth) >= 50 and number($tableWidth) &lt; 70">
								<xsl:attribute name="width">
									<xsl:text>50%</xsl:text>
								</xsl:attribute>
							</xsl:when>
							<xsl:otherwise>
								<xsl:attribute name="width">
									<xsl:text>75%</xsl:text>
								</xsl:attribute>
							</xsl:otherwise>
						</xsl:choose>						
					</xsl:when>
					<xsl:otherwise>
						<xsl:attribute name="width">
							<xsl:text>95%</xsl:text>
						</xsl:attribute>
					</xsl:otherwise>
				</xsl:choose>		

				<xsl:variable name="topbottom">
					<xsl:if test="number(substring-before(@rule-weights,'.'))  &gt; 0">
						<xsl:value-of select="'1'"/>
					</xsl:if>
					<xsl:if test="number(substring-before(@rule-weights,'.'))  = 0">
						<xsl:value-of select="'0'"/>
					</xsl:if>
					<xsl:if
						test="number(substring-before(substring-after(substring-after(@rule-weights, '.'), '.'), '.')) &gt; 0 ">
						<xsl:value-of select="'1'"/>
					</xsl:if>
					<xsl:if
						test="number(substring-before(substring-after(substring-after(@rule-weights, '.'), '.'), '.')) = 0 ">
						<xsl:value-of select="'0'"/>
					</xsl:if>
				</xsl:variable>
				<xsl:variable name="horver">
					<xsl:if
						test="number(substring-before(substring-after(substring-after(substring-after(@rule-weights, '.'), '.'), '.'),'.')) &gt; 0 ">
						<xsl:value-of select="'1'"/>
					</xsl:if>
					<xsl:if
						test="number(substring-before(substring-after(substring-after(substring-after(@rule-weights, '.'), '.'), '.'),'.')) = 0 ">
						<xsl:value-of select="'0'"/>
					</xsl:if>
					<xsl:if
						test="number(substring-before(substring-after(substring-after(substring-after(substring-after(@rule-weights, '.'), '.'), '.'),'.'),'.')) &gt; 0 ">
						<xsl:value-of select="'1'"/>
					</xsl:if>
					<xsl:if
						test="number(substring-before(substring-after(substring-after(substring-after(substring-after(@rule-weights, '.'), '.'), '.'),'.'),'.')) = 0 ">
						<xsl:value-of select="'0'"/>
					</xsl:if>
				</xsl:variable>
				<xsl:attribute name="class">
					<xsl:value-of select="@table-type"/>
				</xsl:attribute>
				<xsl:attribute name="rules">
					<xsl:value-of select="'none'"/>
				</xsl:attribute>
				<xsl:choose>
					<xsl:when test="$topbottom='11'">						
						<xsl:attribute name="style">
							<xsl:text>border-collapse: collapse;</xsl:text>
							<xsl:call-template name="border">
								<xsl:with-param name="side" select="'top'"/>
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="thickness">
									<xsl:value-of
										select="number(substring-before(@rule-weights, '.')) div 2"
									/>px </xsl:with-param>
							</xsl:call-template>
							<xsl:call-template name="border">
								<xsl:with-param name="side" select="'bottom'"/>
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="thickness">
									<xsl:value-of
										select="number(substring-before(substring-after(substring-after(@rule-weights, '.') , '.'),'.')) div 2"
									/>px </xsl:with-param>
							</xsl:call-template>
							<xsl:call-template name="BorderSides">
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="ruleweight" select="@rule-weights"/>
							</xsl:call-template>
						</xsl:attribute>						
					</xsl:when>
					<xsl:when test="$topbottom='10'">
						<xsl:attribute name="style">
							<xsl:text>border-collapse: collapse;</xsl:text>
							<xsl:call-template name="border">
								<xsl:with-param name="side" select="'top'"/>
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="thickness">
									<xsl:value-of
										select="number(substring-before(@rule-weights, '.')) div 2"
									/>px </xsl:with-param>
							</xsl:call-template>
							<xsl:call-template name="border">
								<xsl:with-param name="side" select="'bottom'"/>
								<xsl:with-param name="color" select="'#C0C0C0'"/>
							</xsl:call-template>
							<xsl:call-template name="BorderSides">
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="ruleweight" select="@rule-weights"/>
							</xsl:call-template>
						</xsl:attribute>
					</xsl:when>
					<xsl:when test="$topbottom='01'">
						<xsl:attribute name="style">
							<xsl:text>border-collapse: collapse;</xsl:text>
							<xsl:call-template name="border">
								<xsl:with-param name="side" select="'bottom'"/>
								<xsl:with-param name="color" select="'#C0C0C0'"/>
							</xsl:call-template>
							<xsl:call-template name="border">
								<xsl:with-param name="side" select="'top'"/>
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="thickness">
									<xsl:value-of
										select="number(substring-before(@rule-weights, '.')) div 2"
									/>px </xsl:with-param>
							</xsl:call-template>
							<xsl:call-template name="BorderSides">
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="ruleweight" select="@rule-weights"/>
							</xsl:call-template>
						</xsl:attribute>
					</xsl:when>
					<xsl:when test="$topbottom='00'">
						<xsl:attribute name="style">
							<xsl:text>border-collapse: collapse;</xsl:text>
							<xsl:call-template name="border">
								<xsl:with-param name="side" select="'top'"/>
								<xsl:with-param name="style" select="'solid'"/>
								<xsl:with-param name="color" select="'#C0C0C0'"/>
							</xsl:call-template>
							<xsl:call-template name="border">
								<xsl:with-param name="side" select="'bottom'"/>
								<xsl:with-param name="style" select="'solid'"/>
								<xsl:with-param name="color" select="'#C0C0C0'"/>
							</xsl:call-template>
							<xsl:call-template name="BorderSides">
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="ruleweight" select="@rule-weights"/>
							</xsl:call-template>
						</xsl:attribute>
					</xsl:when>
					<xsl:otherwise>
						<xsl:attribute name="style">
							<xsl:text>border-collapse: collapse;</xsl:text>
							<xsl:call-template name="border">
								<xsl:with-param name="side" select="'top'"/>
								<xsl:with-param name="style" select="'solid'"/>
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="thickness">
									<xsl:value-of
										select="number(substring-before(@rule-weights, '.')) div 2"
									/>px </xsl:with-param>
							</xsl:call-template>
							<xsl:call-template name="border">
								<xsl:with-param name="side" select="'bottom'"/>
								<xsl:with-param name="style" select="'solid'"/>
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="thickness">
									<xsl:value-of
										select="number(substring-before(substring-after(substring-after(@rule-weights, '.') , '.'),'.')) div 2"
									/>px </xsl:with-param>
							</xsl:call-template>
							<xsl:call-template name="BorderSides">
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="ruleweight" select="@rule-weights"/>
							</xsl:call-template>
						</xsl:attribute>
					</xsl:otherwise>
				</xsl:choose>
				<xsl:attribute name="summary">
					<xsl:text>Align to level: </xsl:text>
					<xsl:value-of select="@align-to-level"/>
					<xsl:text>; Subformat: </xsl:text>
					<xsl:value-of select="@subformat"/>
				</xsl:attribute>
				<xsl:apply-templates/>
			</table>
			<!-- tfoot -->
			<xsl:if test="descendant::tfoot">
				<xsl:apply-templates select=".//tfoot" mode="ppp"/>
			</xsl:if>
		</div>
		<xsl:if test="@blank-lines-after">
			<xsl:call-template name="BlankLine">
				<xsl:with-param name="cnt" select="./@blank-lines-after"/>
			</xsl:call-template>
		</xsl:if>
	</xsl:template>
	<!-- table title -->
	<xsl:template match="ttitle">
		<caption align="center" class="ttitle">
			<xsl:choose>
				<xsl:when test="parent::table/@ table-template-name = 'Index to bill and report'">
					<xsl:attribute name="style">
						<xsl:text>font-size: </xsl:text>
						<xsl:value-of select="2 * ../tgroup/@ttitle-size"/>
						<xsl:text>px;</xsl:text>
						<xsl:text>text-transform:uppercase;</xsl:text>						
					</xsl:attribute>
				</xsl:when>
				<xsl:otherwise>
					<xsl:attribute name="style">
						<xsl:text>font-size: </xsl:text>
						<xsl:value-of select="2 * ../tgroup/@ttitle-size"/>
						<xsl:text>px</xsl:text>
					</xsl:attribute>
				</xsl:otherwise>
			</xsl:choose>
			
			<xsl:if test="name(../..)='quoted-block'">
				<xsl:if test="string-length(normalize-space(.)) &gt; 0 ">
					<xsl:text disable-output-escaping="yes">“</xsl:text>
				</xsl:if>
			</xsl:if>
			<xsl:if test="parent::table/@ table-template-name = 'Index to bill and report'">
				<br/>
			</xsl:if>
			<xsl:apply-templates/>
			
			<xsl:if test="parent::table/@ table-template-name = 'Index to bill and report'">
				<br/>
				<br/>
				<hr width="60"/>
				<br/>
				<br/>				
			</xsl:if>
		</caption>
	</xsl:template>
	<!-- table subtitle -->
	<xsl:template match="tdesc">
		<caption align="center" class="tdesc">
			<xsl:attribute name="style">
				<xsl:text>font-size: </xsl:text>
				<xsl:value-of select="2.2 * (../tgroup/@ttitle-size - 2)"/>
				<xsl:text>px</xsl:text>
			</xsl:attribute>
			<xsl:if test="name(../..)='quoted-block'">
				<xsl:if
					test="string-length(normalize-space( .)) &gt; 0 and string-length(../ttitle) =0 ">
					<xsl:text disable-output-escaping="yes">“</xsl:text>
				</xsl:if>
			</xsl:if>
			<xsl:apply-templates/>
		</caption>
	</xsl:template>
	<!-- column spec -->
	<xsl:template match="colspec">
		<xsl:variable name="TotalLen">
			<xsl:choose>
				<xsl:when
					test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 6">
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'txt')]/@min-data-value) + sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *3.5"
					/>
				</xsl:when>
				<xsl:when
					test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 7">
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'txt')]/@min-data-value) + sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *4"
					/>
				</xsl:when>
				<xsl:when
					test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 8">
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'txt')]/@min-data-value) + sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *4.5"
					/>
				</xsl:when>
				<xsl:when
					test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 9">
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'txt')]/@min-data-value) + sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *5"
					/>
				</xsl:when>
				<xsl:when
					test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 10">
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'txt')]/@min-data-value) + sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *6"
					/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'txt')]/@min-data-value) + sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *5"
					/>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:variable name="TotLength">
			<xsl:if test="not(number($TotalLen))">
				<xsl:value-of select="'1'"/>
			</xsl:if>
			<xsl:if test="number($TotalLen)">
				<xsl:value-of select="$TotalLen"/>
			</xsl:if>
		</xsl:variable>
		<xsl:variable name="TotalLenTxt">
			<xsl:value-of select="sum(../colspec[contains(@coldef, 'txt')]/@min-data-value)"/>
		</xsl:variable>
		<xsl:variable name="TotalLenFig">
			<xsl:choose>
				<xsl:when
					test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 6">
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *3.5"/>
				</xsl:when>
				<xsl:when
					test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 7">
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *4"/>
				</xsl:when>
				<xsl:when
					test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 8">
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *4.5"/>
				</xsl:when>
				<xsl:when
					test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 9">
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *5"/>
				</xsl:when>
				<xsl:when
					test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 10">
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *6"/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of
						select="sum(../colspec[contains(@coldef, 'fig')]/@min-data-value) *5"/>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<col>
			<xsl:attribute name="class">
				<xsl:value-of select="@colname"/>
			</xsl:attribute>
			<xsl:if test="contains(@coldef , 'fig')">
				<xsl:choose>
					<xsl:when
						test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 6">
						<xsl:attribute name="width">
							<xsl:value-of select="round(((@min-data-value * 3.5)))"/>
						</xsl:attribute>
					</xsl:when>
					<xsl:when
						test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 7">
						<xsl:attribute name="width">
							<xsl:value-of select="round(((@min-data-value * 4)))"/>
						</xsl:attribute>
					</xsl:when>
					<xsl:when
						test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 8">
						<xsl:attribute name="width">
							<xsl:value-of select="round(((@min-data-value * 4.5)))"/>
						</xsl:attribute>
					</xsl:when>
					<xsl:when
						test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 9">
						<xsl:attribute name="width">
							<xsl:value-of select="round(((@min-data-value * 5)))"/>
						</xsl:attribute>
					</xsl:when>
					<xsl:when
						test="number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'), '.')) = 10">
						<xsl:attribute name="width">
							<xsl:value-of select="round(((@min-data-value * 6)))"/>
						</xsl:attribute>
					</xsl:when>
					<xsl:otherwise>
						<xsl:attribute name="width">
							<xsl:value-of select="round(((@min-data-value * 5)))"/>
						</xsl:attribute>
					</xsl:otherwise>
				</xsl:choose>
			</xsl:if>
			<xsl:if test="number(ancestor::table/tgroup/@cols) &gt; 3">
				<xsl:if test="not(contains(@coldef , 'fig'))">
					<!--<xsl:attribute name="width"><xsl:value-of select="round((translate(@min-data-value, 'nbp','') div number($TotLength)) * 100)"/>%</xsl:attribute>-->
					<xsl:attribute name="width">
						<xsl:value-of
							select="(number(translate(@min-data-value, 'nbp','')) div number($TotalLenTxt)) * (1180 - $TotalLenFig)"
						/>
					</xsl:attribute>
				</xsl:if>
			</xsl:if>
			<xsl:if test="number(ancestor::table/tgroup/@cols) = 3">
				<xsl:if test="not(contains(@coldef , 'fig'))">
					<!--<xsl:attribute name="width"><xsl:value-of select="round((translate(@min-data-value, 'nbp','') div number($TotLength)) * 100)"/>%</xsl:attribute>-->
					<xsl:attribute name="width">
						<xsl:value-of
							select="(number(translate(@min-data-value, 'nbp','')) div number($TotalLenTxt)) * (1180* 0.6 - $TotalLenFig)"
						/>
					</xsl:attribute>
				</xsl:if>
			</xsl:if>
			<xsl:if test="number(ancestor::table/tgroup/@cols) &lt; 3">
				<xsl:if test="not(contains(@coldef , 'fig'))">
					<!--<xsl:attribute name="width"><xsl:value-of select="round((translate(@min-data-value, 'nbp','') div number($TotLength)) * 100)"/>%</xsl:attribute>-->
					<xsl:if
						test="@min-data-value=0 and contains(ancestor::table/@table-type, 'subformat')">
						<xsl:if test="ancestor::table/@table-type='subformat-2-Tax-Rate'">
							<xsl:if test="count(preceding-sibling::colspec)=0">
								<xsl:attribute name="width">50%</xsl:attribute>
							</xsl:if>
							<xsl:if test="count(preceding-sibling::colspec)=1">
								<xsl:attribute name="width">50%</xsl:attribute>
							</xsl:if>
						</xsl:if>
						<xsl:if test="not(ancestor::table/@table-type='subformat-2-Tax-Rate')">
							<xsl:if test="count(preceding-sibling::colspec)=0">
								<xsl:attribute name="width">85%</xsl:attribute>
							</xsl:if>
							<xsl:if test="count(preceding-sibling::colspec)=1">
								<xsl:attribute name="width">15%</xsl:attribute>
							</xsl:if>
						</xsl:if>
					</xsl:if>
					<xsl:if
						test="not(@min-data-value=0 and contains(ancestor::table/@table-type, 'subformat'))">
						<xsl:attribute name="width">
							<xsl:value-of
								select="(number(translate(@min-data-value, 'nbp','')) div number($TotalLenTxt)) * (1180* 0.4 - $TotalLenFig)"
							/>
						</xsl:attribute>
					</xsl:if>
				</xsl:if>
			</xsl:if>
			<xsl:attribute name="align">
				<xsl:value-of select="@align"/>
			</xsl:attribute>
		</col>
	</xsl:template>
	<!-- table rows -->
	<xsl:template match="row">
		<tr>
			<xsl:apply-templates/>
		</tr>
	</xsl:template>
	<!-- table head /table body -->
	<xsl:template match="thead|tbody">
		<xsl:element name="{name()}">
			<xsl:attribute name="style">
				<xsl:choose>
					<xsl:when test="name()='thead'">
						<xsl:if test="../@thead-tbody-ldg-size">
							<xsl:text>font-size: </xsl:text>
							<xsl:value-of
								select="1.7* number(substring-before(../@thead-tbody-ldg-size, '.'))"/>
							<xsl:text>px</xsl:text>
						</xsl:if>
					</xsl:when>
					<xsl:when test="name()='tbody'">
						<xsl:if test="../@thead-tbody-ldg-size">
							<xsl:text>font-size: </xsl:text>
							<xsl:value-of
								select="1.7* number(substring-before(substring-after(../@thead-tbody-ldg-size, '.'),'.'))"/>
							<xsl:text>px</xsl:text>
						</xsl:if>
					</xsl:when>
				</xsl:choose>
			</xsl:attribute>
			<xsl:apply-templates/>
		</xsl:element>
	</xsl:template>

	<!-- skip tfoot -->
	<xsl:template match="tfoot"> </xsl:template>

	<!-- make up another template table for tfoot -->
	<xsl:template match="tfoot" mode="ppp">
		<table cellpadding="0" cellspacing="0">
			<xsl:apply-templates/>
		</table>
	</xsl:template>

	<!-- row of tfoot -->
	<xsl:template match="tfoot/row">
		<tr>
			<xsl:apply-templates/>
		</tr>
	</xsl:template>
	<!-- entry of tfoot -->
	<xsl:template match="tfoot//entry">
		<td>
			<xsl:attribute name="class">
				<xsl:value-of select="'tfoot'"/>
			</xsl:attribute>
			<xsl:attribute name="align">
				<xsl:value-of select="@align"/>
			</xsl:attribute>
			<xsl:if test="@namest and @nameend">
				<xsl:attribute name="colspan">
					<xsl:value-of
						select="number(translate(@nameend, 'col','')) - number(translate(@namest, 'col',''))+1"
					/>
				</xsl:attribute>
			</xsl:if>
			<xsl:if test="@morerows">
				<xsl:attribute name="rowspan">
					<xsl:value-of select="@morerows + 1"/>
				</xsl:attribute>
			</xsl:if>
			<xsl:attribute name="style">
				<xsl:if test="ancestor::tgroup/@bearoff">
					<xsl:text>padding-left: </xsl:text>
					<xsl:value-of select="number(ancestor::tgroup/@bearoff) + 5"/>
					<xsl:text>px; </xsl:text>
					<xsl:text>padding-right: </xsl:text>
					<xsl:text>1px; </xsl:text>
				</xsl:if>
				<xsl:if test="not(ancestor::tgroup/@bearoff)">
					<xsl:text>padding-left:5px;padding-right:1px;</xsl:text>
				</xsl:if>
				<xsl:if test="ancestor::tgroup/@fnote-size">
					<xsl:text>font-size: </xsl:text>
					<xsl:value-of select="ancestor::tgroup/@fnote-size * 2.2"/>
					<xsl:text>px</xsl:text>
				</xsl:if>
				<xsl:if test="not(ancestor::tgroup/@fnote-size)">
					<xsl:text>font-size: 16px</xsl:text>
				</xsl:if>
			</xsl:attribute>
			<xsl:apply-templates/>
		</td>
	</xsl:template>

	<!-- thead entry -->
	<xsl:template match="//thead//entry">
		<td>
			<xsl:attribute name="class">
				<xsl:value-of select="@colname"/>
			</xsl:attribute>
			<!-- no wrap for subformat table headers -->
			<xsl:if test="@colname='I50' or @colname='I46' or @colname='I47' or @colname='I48'">
				<xsl:attribute name="NOWRAP"/>
			</xsl:if>
			<xsl:attribute name="align">
				<xsl:value-of select="@align"/>
			</xsl:attribute>
			<xsl:if test="@namest and @nameend">
				<xsl:attribute name="colspan">
					<xsl:choose>
						<xsl:when test="contains(@nameend, 'column')">
							<xsl:value-of
								select="number(translate(@nameend, 'column','')) - number(translate(@namest, 'column',''))+1"
							/>
						</xsl:when>
						<xsl:otherwise>
							<xsl:value-of
								select="number(translate(@nameend, 'col','')) - number(translate(@namest, 'col',''))+1"
							/>
						</xsl:otherwise>
					</xsl:choose>

				</xsl:attribute>
			</xsl:if>
			<xsl:if test="@morerows">
				<xsl:attribute name="rowspan">
					<xsl:value-of select="@morerows + 1"/>
				</xsl:attribute>
			</xsl:if>
			<!-- Bottom of thead: inherit from @rule-weights -->
			<xsl:if test="../@rowsep='1'">
				<xsl:attribute name="style">
					<xsl:if test="ancestor::tgroup/@bearoff">
						<xsl:text>padding-left: </xsl:text>
						<xsl:value-of select="number(ancestor::tgroup/@bearoff) + 5"/>
						<xsl:text>px; </xsl:text>
						<xsl:text>padding-right: </xsl:text>
						<xsl:text>1px; </xsl:text>
					</xsl:if>
					<xsl:if test="not(ancestor::tgroup/@bearoff)">
						<xsl:text>padding-left:5px;padding-right:1px;</xsl:text>
					</xsl:if>
					<xsl:if test="count(../preceding-sibling::row) = 0">
						<xsl:if
							test="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.')) &gt; 0">
							<xsl:text>border-bottom:</xsl:text><xsl:value-of
								select="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.'))  div 2"
							/>px<xsl:text> solid #C0C0C0</xsl:text>
						</xsl:if>
						<xsl:if
							test="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.')) = 0">
							<xsl:text>border-bottom-width:0px</xsl:text>
						</xsl:if>
					</xsl:if>
					<xsl:if test="count(../preceding-sibling::row) &gt; 0">
						<xsl:text>border-bottom:</xsl:text><xsl:value-of
							select="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.'))  div 2"
						/>px<xsl:text> solid #C0C0C0</xsl:text>
					</xsl:if>
					<xsl:text>; </xsl:text>

					<xsl:variable name="currColname">
						<xsl:if test="@colname">
							<xsl:value-of select="@colname"/>
						</xsl:if>
						<xsl:if test="not(@colname)">
							<xsl:value-of select="@namest"/>
						</xsl:if>
					</xsl:variable>
					<!-- last column, there is no colsep -->
					<xsl:if
						test="count(following-sibling::entry) &gt; 0 or (number(translate(@nameend, 'col','')) &lt; ancestor::tgroup/@cols)">
						<xsl:if test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep='1'">
							<xsl:choose>
								<xsl:when
									test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep-modify='bold'">
									<xsl:call-template name="ColSep">
										<xsl:with-param name="color" select="'#C0C0C0'"/>
										<xsl:with-param name="style" select="'solid'"/>
										<xsl:with-param name="ruleweight"
											select="ancestor::table/@rule-weights"/>
									</xsl:call-template>
								</xsl:when>
								<xsl:when
									test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep-modify='parallel'">
									<xsl:call-template name="ColSep">
										<xsl:with-param name="color" select="'#C0C0C0'"/>
										<xsl:with-param name="style" select="'double'"/>
										<xsl:with-param name="ruleweight"
											select="ancestor::table/@rule-weights"/>
									</xsl:call-template>
								</xsl:when>
								<xsl:otherwise>
									<xsl:call-template name="ColSep">
										<xsl:with-param name="color" select="'#C0C0C0'"/>
										<xsl:with-param name="style" select="'solid'"/>
										<xsl:with-param name="ruleweight"
											select="ancestor::table/@rule-weights"/>
									</xsl:call-template>
								</xsl:otherwise>
							</xsl:choose>
						</xsl:if>
					</xsl:if>
				</xsl:attribute>
			</xsl:if>
			<xsl:if test="not(../@rowsep='1') ">
				<xsl:if test="@rowsep='1'">
					<xsl:attribute name="style">
						<xsl:if test="ancestor::tgroup/@bearoff">
							<xsl:text>padding-left: </xsl:text>
							<xsl:value-of select="number(ancestor::tgroup/@bearoff) + 5"/>
							<xsl:text>px; </xsl:text>
							<xsl:text>padding-right: </xsl:text>
							<xsl:text>1px; </xsl:text>
						</xsl:if>
						<xsl:if test="not(ancestor::tgroup/@bearoff)">
							<xsl:text>padding-left:5px;padding-right:1px;</xsl:text>
						</xsl:if>
						<xsl:if test="count(../preceding-sibling::row) = 0">
							<xsl:if
								test="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.')) &gt; 0">
								<xsl:text>border-bottom:</xsl:text><xsl:value-of
									select="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.'))  div 2"
								/>px<xsl:text> solid #C0C0C0</xsl:text>
							</xsl:if>
							<xsl:if
								test="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.')) = 0">
								<!-- surpress rowsep in subformat tables -->
								<xsl:if
									test="(starts-with(ancestor::table/@table-type, 'subformat'))">
									<xsl:text>border-bottom:0px solid #FFFFFF</xsl:text>
								</xsl:if>
								<xsl:if
									test="not(starts-with(ancestor::table/@table-type, 'subformat'))">
									<!--<xsl:text>border-bottom:thin solid #C0C0C0</xsl:text>-->
									<xsl:text>border-bottom:0px solid #FFFFFF</xsl:text>
								</xsl:if>
							</xsl:if>
						</xsl:if>
						<xsl:if test="count(../preceding-sibling::row) &gt; 0">
							<!-- surpress rowsep in subformat tables -->
							<xsl:if test="(starts-with(ancestor::table/@table-type, 'subformat'))">
								<xsl:text>border-bottom:</xsl:text><xsl:value-of
									select="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.'))  div 2"
								/>px<xsl:text> solid #FFFFFF</xsl:text>
							</xsl:if>
							<xsl:if
								test="not(starts-with(ancestor::table/@table-type, 'subformat'))">
								<xsl:text>border-bottom:</xsl:text><xsl:value-of
									select="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.'))  div 2"
								/>px<xsl:text> solid #C0C0C0</xsl:text>
							</xsl:if>
						</xsl:if>
						<xsl:text>; </xsl:text>
						<xsl:variable name="currColname">
							<xsl:if test="not(@colname)">
								<xsl:value-of select="@namest"/>
							</xsl:if>
							<xsl:if test="@colname">
								<xsl:value-of select="@colname"/>
							</xsl:if>
						</xsl:variable>
						<xsl:if
							test="count(following-sibling::entry) &gt; 0 or (number(translate(@nameend, 'col','')) &lt; ancestor::tgroup/@cols)">
							<xsl:if
								test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep='1'">
								<xsl:choose>
									<xsl:when
										test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep-modify='bold'">
										<xsl:call-template name="ColSep">
											<xsl:with-param name="color" select="'#C0C0C0'"/>
											<xsl:with-param name="style" select="'solid'"/>
											<xsl:with-param name="ruleweight"
												select="ancestor::table/@rule-weights"/>
										</xsl:call-template>
									</xsl:when>
									<xsl:when
										test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep-modify='parallel'">
										<xsl:call-template name="ColSep">
											<xsl:with-param name="color" select="'#C0C0C0'"/>
											<xsl:with-param name="style" select="'double'"/>
											<xsl:with-param name="ruleweight"
												select="ancestor::table/@rule-weights"/>
										</xsl:call-template>
									</xsl:when>
									<xsl:otherwise>
										<xsl:call-template name="ColSep">
											<xsl:with-param name="color" select="'#C0C0C0'"/>
											<xsl:with-param name="style" select="'solid'"/>
											<xsl:with-param name="ruleweight"
												select="ancestor::table/@rule-weights"/>
										</xsl:call-template>
									</xsl:otherwise>
								</xsl:choose>
							</xsl:if>
						</xsl:if>
						<xsl:if
							test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep='0' or not(ancestor::tgroup/colspec[@colname=$currColname]/@colsep)">
							<xsl:call-template name="ColSep">
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="style" select="'solid'"/>
								<xsl:with-param name="ruleweight"
									select="ancestor::table/@rule-weights"/>
							</xsl:call-template>
						</xsl:if>
					</xsl:attribute>
				</xsl:if>

				<xsl:if test="@rowsep='0' or not(@rowsep)">
					<xsl:attribute name="style">
						<xsl:if test="ancestor::tgroup/@bearoff">
							<xsl:text>padding-left: </xsl:text>
							<xsl:value-of select="number(ancestor::tgroup/@bearoff) + 5"/>
							<xsl:text>px; </xsl:text>
							<xsl:text>padding-right: </xsl:text>
							<xsl:text>1px; </xsl:text>
						</xsl:if>
						<xsl:if test="not(ancestor::tgroup/@bearoff)">
							<xsl:text>padding-left:5px;padding-right:1px;</xsl:text>
						</xsl:if>
						<xsl:if test="count(../following-sibling::row) = 0">
							<xsl:if test="ancestor::table/@rule-weights">
								<xsl:if
									test="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.')) &gt; 0">
									<xsl:text>border-bottom:thin solid #C0C0C0</xsl:text>
								</xsl:if>
								<xsl:if
									test="number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.')) = 0">
									<!--<xsl:text>border-bottom:thin solid #C0C0C0</xsl:text>-->
									<xsl:text>border-bottom:0px solid #FFFFFF</xsl:text>
								</xsl:if>
							</xsl:if>
							<xsl:if test="not(ancestor::table/@rule-weights)">
								<!-- surpress rowsep in subformat tables -->
								<xsl:if
									test="(starts-with(ancestor::table/@table-type, 'subformat'))">
									<xsl:text>border-bottom:0px solid #FFFFFF</xsl:text>
								</xsl:if>
								<xsl:if
									test="(starts-with(ancestor::table/@table-type, 'subformat'))">
									<!--<xsl:text>border-bottom:thin solid #C0C0C0</xsl:text>-->
									<xsl:text>border-bottom:0px solid #FFFFFF</xsl:text>
								</xsl:if>
							</xsl:if>
						</xsl:if>
						<xsl:if test="count(../following-sibling::row) &gt; 0 ">
							<xsl:if
								test="not(ancestor::table/@rule-weights) or number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.')) = 0">
								<!-- surpress rowsep in subformat tables -->
								<xsl:if
									test="(starts-with(ancestor::table/@table-type, 'subformat'))">
									<xsl:text>border-bottom:0px solid #FFFFFF</xsl:text>
								</xsl:if>
								<xsl:if
									test="not(starts-with(ancestor::table/@table-type, 'subformat'))">
									<!--<xsl:text>border-bottom:thin solid #C0C0C0</xsl:text>-->
									<xsl:text>border-bottom:0px solid #FFFFFF</xsl:text>
								</xsl:if>
							</xsl:if>
							<xsl:if
								test="ancestor::table/@rule-weights and number(substring-before(substring-after(ancestor::table/@rule-weights, '.'), '.')) &gt; 0">
								<xsl:text>border-bottom:thin solid #C0C0C0</xsl:text>
							</xsl:if>
						</xsl:if>
						<xsl:text>; </xsl:text>
						<xsl:variable name="currColname">
							<xsl:if test="not(@colname)">
								<xsl:value-of select="@namest"/>
							</xsl:if>
							<xsl:if test="@colname">
								<xsl:value-of select="@colname"/>
							</xsl:if>
						</xsl:variable>
						<xsl:if
							test="count(following-sibling::entry) &gt; 0 or (number(translate(@nameend, 'col','')) &lt; ancestor::tgroup/@cols)">
							<xsl:if
								test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep='1'">
								<xsl:choose>
									<xsl:when
										test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep-modify='bold'">
										<xsl:call-template name="ColSep">
											<xsl:with-param name="color" select="'#C0C0C0'"/>
											<xsl:with-param name="style" select="'solid'"/>
											<xsl:with-param name="ruleweight"
												select="ancestor::table/@rule-weights"/>
										</xsl:call-template>
									</xsl:when>
									<xsl:when
										test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep-modify='parallel'">
										<xsl:call-template name="ColSep">
											<xsl:with-param name="color" select="'#C0C0C0'"/>
											<xsl:with-param name="style" select="'double'"/>
											<xsl:with-param name="ruleweight"
												select="ancestor::table/@rule-weights"/>
										</xsl:call-template>
									</xsl:when>
									<xsl:otherwise>
										<xsl:call-template name="ColSep">
											<xsl:with-param name="color" select="'#C0C0C0'"/>
											<xsl:with-param name="style" select="'solid'"/>
											<xsl:with-param name="ruleweight"
												select="ancestor::table/@rule-weights"/>
										</xsl:call-template>
									</xsl:otherwise>
								</xsl:choose>
							</xsl:if>
						</xsl:if>
						<xsl:if
							test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep='0' or not(ancestor::tgroup/colspec[@colname=$currColname]/@colsep)">
							<xsl:call-template name="ColSep">
								<xsl:with-param name="color" select="'#C0C0C0'"/>
								<xsl:with-param name="style" select="'solid'"/>
								<xsl:with-param name="ruleweight"
									select="ancestor::table/@rule-weights"/>
							</xsl:call-template>
						</xsl:if>
					</xsl:attribute>
				</xsl:if>
			</xsl:if>

			<xsl:if test="not(starts-with(ancestor::table/@table-type, 'subformat'))">
				<xsl:if test="count(preceding-sibling::entry) =0">
					<xsl:if test="count(../preceding-sibling::row) =0">
						<xsl:if test="ancestor::quoted-block">
							<xsl:if
								test="string-length(normalize-space( .)) &gt; 0 and string-length(ancestor::table/ttitle) = 0 and string-length(ancestor::table/tdesc) =0 ">
								<xsl:text disable-output-escaping="yes">“</xsl:text>
							</xsl:if>
						</xsl:if>
					</xsl:if>
				</xsl:if>
			</xsl:if>
			<xsl:if test="(starts-with(ancestor::table/@table-type, 'subformat'))">
				<xsl:if test="count(preceding-sibling::entry) =0">
					<xsl:if test="count(../preceding-sibling::row) =0">
						<xsl:if test="ancestor::quoted-block">
							<xsl:if
								test="string-length(normalize-space( .)) &gt; 0 and string-length(ancestor::table/ttitle) = 0 and string-length(ancestor::table/tdesc) =0 ">
								<xsl:text disable-output-escaping="yes">“</xsl:text>
							</xsl:if>
						</xsl:if>
					</xsl:if>
				</xsl:if>
				<xsl:if test="count(preceding-sibling::entry) =0">
					<xsl:if test="count(../preceding-sibling::row) =1">
						<xsl:if test="string-length(../preceding-sibling::row[1]/entry[1]) = 0 ">
							<xsl:if test="ancestor::quoted-block">
								<xsl:if
									test="string-length(normalize-space( .)) &gt; 0 and string-length(ancestor::table/ttitle) = 0 and string-length(ancestor::table/tdesc) =0 ">
									<xsl:text disable-output-escaping="yes">“</xsl:text>
								</xsl:if>
							</xsl:if>
						</xsl:if>
					</xsl:if>
				</xsl:if>
			</xsl:if>
			<xsl:apply-templates/>
		</td>
	</xsl:template>

	<!-- regular entry -->
	<xsl:template match="//tbody//entry">
		<xsl:variable name="isFirstNonEmptyEntry">
			<xsl:call-template name="isFirstNonemptyColumn"/>
		</xsl:variable>
		<td>
			<xsl:variable name="currColname">
				<xsl:if test="@colname">
					<xsl:value-of select="@colname"/>
				</xsl:if>
				<xsl:if test="not(@colname)">
					<xsl:value-of select="@namest"/>
				</xsl:if>
			</xsl:variable>
			<xsl:attribute name="class">
				<xsl:if test="count(preceding-sibling::entry) = 0 ">
					<xsl:if test="@stub-definition='txt-ldr'">
						<xsl:if test="count(following-sibling::entry)=0">
							<xsl:value-of select="@colname"/>
						</xsl:if>
						<xsl:if test="count(following-sibling::entry) &gt; 0">
							<xsl:value-of select="'dot-leader'"/>
						</xsl:if>
					</xsl:if>
				</xsl:if>
				<xsl:if test="count(preceding-sibling::entry) &gt; 0 ">
					<xsl:if test="count(following-sibling::entry) =0">
						<xsl:if
							test="contains(ancestor::tgroup/colspec[@colname=$currColname]/@coldef, 'txt')">
							<xsl:value-of select="@colname"/>
						</xsl:if>
						<xsl:if
							test="not(contains(ancestor::tgroup/colspec[@colname=$currColname]/@coldef, 'txt'))">
							<xsl:if test="string-length(.) =0">
								<xsl:if test="contains(ancestor::table/@table-type, 'Duty')">
									<xsl:value-of select="@colname"/>
								</xsl:if>
								<xsl:if test="not(contains(ancestor::table/@table-type, 'Duty'))">
									<xsl:if test="not(@align='center')">
										<xsl:value-of select="'dot-leader'"/>
									</xsl:if>
								</xsl:if>
							</xsl:if>
						</xsl:if>
					</xsl:if>
					<xsl:if test="count(following-sibling::entry) &gt; 0">
						<xsl:if test="@leader-modify='force-ldr'">
							<xsl:value-of select="'dot-leader'"/>
						</xsl:if>
						<xsl:if test="not(@leader-modify='force-ldr')">
							<xsl:value-of select="@colname"/>
						</xsl:if>
					</xsl:if>
				</xsl:if>
			</xsl:attribute>
			<xsl:attribute name="align">
				<xsl:value-of select="@align"/>
			</xsl:attribute>
			<!-- vertical alignment-->
			<xsl:if test="not(@valign) and not(contains(ancestor::table/@table-type, 'Duty'))">
				<xsl:attribute name="valign">
					<xsl:if
						test="contains(ancestor::tgroup/colspec[@colname=$currColname]/@coldef, 'fig')">
						<xsl:value-of select="'bottom'"/>
					</xsl:if>
					<xsl:if
						test="contains(ancestor::tgroup/colspec[@colname=$currColname]/@coldef, 'txt')">
						<xsl:value-of select="'top'"/>
					</xsl:if>
				</xsl:attribute>
			</xsl:if>
			<xsl:if test="not(@valign) and (contains(ancestor::table/@table-type, 'Duty'))">
				<xsl:attribute name="valign">
					<xsl:value-of select="'top'"/>
				</xsl:attribute>
			</xsl:if>
			<xsl:if test="@valign">
				<xsl:attribute name="valign">
					<xsl:value-of select="@valign"/>
				</xsl:attribute>
			</xsl:if>

			<xsl:if test="@namest and @nameend">
				<xsl:attribute name="colspan">
					<xsl:value-of
						select="number(translate(@nameend, 'col','')) - number(translate(@namest, 'col',''))+1"
					/>
				</xsl:attribute>
			</xsl:if>
			<xsl:if test="@morerows">
				<xsl:attribute name="rowspan">
					<xsl:value-of select="@morerows + 1"/>
				</xsl:attribute>
			</xsl:if>
			<!-- style attribute -->
			<xsl:attribute name="style">
				<xsl:if test="ancestor::tgroup/@bearoff">
					<xsl:text>padding-left: </xsl:text>
					<xsl:text>-4px; </xsl:text>
					<xsl:text>padding-right: </xsl:text>
					<xsl:text>-4px; </xsl:text>
				</xsl:if>				
				<!-- colsep -->
				<xsl:if
					test="count(following-sibling::entry) &gt; 0 or (number(translate(@nameend, 'col','')) &lt; ancestor::tgroup/@cols)">
					<xsl:if test="@colsep='1'">
						<xsl:call-template name="ColSep">
							<xsl:with-param name="color" select="'#C0C0C0'"/>
							<xsl:with-param name="style" select="'solid'"/>
							<xsl:with-param name="ruleweight" select="ancestor::table/@rule-weights"
							/>
						</xsl:call-template>
					</xsl:if>
				</xsl:if>
				<xsl:if test="@colsep='0'">
					<xsl:call-template name="ColSep">
						<xsl:with-param name="color" select="'#C0C0C0'"/>
						<xsl:with-param name="style" select="'solid'"/>
						<xsl:with-param name="ruleweight" select="ancestor::table/@rule-weights"/>
					</xsl:call-template>
				</xsl:if>
				<!-- inherit from colspec -->
				<xsl:if test="not(@colsep)">
					<xsl:if
						test="count(following-sibling::entry) &gt; 0 or (number(translate(@nameend, 'col','')) &lt; ancestor::tgroup/@cols)">
						<xsl:if test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep='1'">
							<xsl:choose>
								<xsl:when
									test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep-modify='bold'">
									<xsl:call-template name="ColSep">
										<xsl:with-param name="color" select="'#C0C0C0'"/>
										<xsl:with-param name="style" select="'solid'"/>
										<xsl:with-param name="ruleweight"
											select="ancestor::table/@rule-weights"/>
									</xsl:call-template>
								</xsl:when>
								<xsl:when
									test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep-modify='parallel'">
									<xsl:call-template name="ColSep">
										<xsl:with-param name="color" select="'#C0C0C0'"/>
										<xsl:with-param name="style" select="'double'"/>
										<xsl:with-param name="ruleweight"
											select="ancestor::table/@rule-weights"/>
									</xsl:call-template>
								</xsl:when>
								<xsl:otherwise>
									<xsl:call-template name="ColSep">
										<xsl:with-param name="color" select="'#C0C0C0'"/>
										<xsl:with-param name="style" select="'solid'"/>
										<xsl:with-param name="ruleweight"
											select="ancestor::table/@rule-weights"/>
									</xsl:call-template>
								</xsl:otherwise>
							</xsl:choose>
						</xsl:if>
					</xsl:if>
					<xsl:if
						test="ancestor::tgroup/colspec[@colname=$currColname]/@colsep='0' or not(ancestor::tgroup/colspec[@colname=$currColname]/@colsep)">
						<xsl:call-template name="ColSep">
							<xsl:with-param name="color" select="'#C0C0C0'"/>
							<xsl:with-param name="style" select="'solid'"/>
							<xsl:with-param name="ruleweight" select="ancestor::table/@rule-weights"
							/>
						</xsl:call-template>
					</xsl:if>
				</xsl:if>
				<xsl:text>; </xsl:text>

				<!-- rowsep -->
				<xsl:if test="count(../following-sibling::row) &gt; 0">
					<xsl:if test="@rowsep='1'">
						<xsl:choose>
							<xsl:when test="@rowsep-modify='bold'">
								<xsl:call-template name="RowSep">
									<xsl:with-param name="color" select="'#C0C0C0'"/>
									<xsl:with-param name="style" select="'solid'"/>
									<xsl:with-param name="ruleweight"
										select="ancestor::table/@rule-weights"/>
								</xsl:call-template>
							</xsl:when>
							<xsl:when test="@rowsep-modify='double'">
								<xsl:call-template name="RowSep">
									<xsl:with-param name="color" select="'#C0C0C0'"/>
									<xsl:with-param name="style" select="'double'"/>
									<xsl:with-param name="ruleweight"
										select="ancestor::table/@rule-weights"/>
								</xsl:call-template>
							</xsl:when>
							<xsl:otherwise>
								<xsl:call-template name="RowSep">
									<xsl:with-param name="color" select="'#C0C0C0'"/>
									<xsl:with-param name="style" select="'solid'"/>
									<xsl:with-param name="ruleweight"
										select="ancestor::table/@rule-weights"/>
								</xsl:call-template>
							</xsl:otherwise>
						</xsl:choose>
					</xsl:if>

					<xsl:if test="@rowsep='0'">
						<xsl:call-template name="RowSep">
							<!--<xsl:with-param name="color" select="'#C0C0C0'"/>-->
							<xsl:with-param name="color" select="'#FFFFFF'"/>
							<xsl:with-param name="style" select="'solid'"/>
							<xsl:with-param name="ruleweight" select="'0.0.0.0.0.0'"/>
						</xsl:call-template>
					</xsl:if>
					<!-- inherit from row level-->
					<xsl:if test="not(@rowsep)">
						<xsl:if test="../@rowsep='1'">
							<xsl:choose>
								<xsl:when test="../@rowsep-modify='bold'">
									<xsl:call-template name="RowSep">
										<xsl:with-param name="color" select="'#C0C0C0'"/>
										<xsl:with-param name="style" select="'solid'"/>
										<xsl:with-param name="ruleweight"
											select="ancestor::table/@rule-weights"/>
									</xsl:call-template>
								</xsl:when>
								<xsl:when test="../@rowsep-modify='double'">
									<xsl:call-template name="RowSep">
										<xsl:with-param name="color" select="'#C0C0C0'"/>
										<xsl:with-param name="style" select="'double'"/>
										<xsl:with-param name="ruleweight"
											select="ancestor::table/@rule-weights"/>
									</xsl:call-template>
								</xsl:when>
								<xsl:otherwise>
									<xsl:call-template name="RowSep">
										<xsl:with-param name="color" select="'#C0C0C0'"/>
										<xsl:with-param name="style" select="'solid'"/>
										<xsl:with-param name="ruleweight"
											select="ancestor::table/@rule-weights"/>
									</xsl:call-template>
								</xsl:otherwise>
							</xsl:choose>
						</xsl:if>

						<xsl:if test="(../@rowsep='0') ">
							<xsl:call-template name="RowSep">
								<!--<xsl:with-param name="color" select="'#C0C0C0'"/>-->
								<xsl:with-param name="color" select="'#FFFFFF'"/>
								<xsl:with-param name="style" select="'solid'"/>
								<xsl:with-param name="ruleweight" select="'0.0.0.0.0.0'"/>
							</xsl:call-template>
						</xsl:if>

						<!-- inherit from colspec -->
						<xsl:if test="not(../@rowsep)">
							<xsl:if
								test="ancestor::tgroup/colspec[@colname=$currColname]/@rowsep='1'">
								<xsl:choose>
									<xsl:when test="../@rowsep-modify='bold'">
										<xsl:call-template name="RowSep">
											<xsl:with-param name="color" select="'#C0C0C0'"/>
											<xsl:with-param name="style" select="'solid'"/>
											<xsl:with-param name="ruleweight"
												select="ancestor::table/@rule-weights"/>
										</xsl:call-template>
									</xsl:when>
									<xsl:when test="../@rowsep-modify='double'">
										<xsl:call-template name="RowSep">
											<xsl:with-param name="color" select="'#C0C0C0'"/>
											<xsl:with-param name="style" select="'double'"/>
											<xsl:with-param name="ruleweight"
												select="ancestor::table/@rule-weights"/>
										</xsl:call-template>
									</xsl:when>
									<xsl:otherwise>
										<xsl:call-template name="RowSep">
											<xsl:with-param name="color" select="'#C0C0C0'"/>
											<xsl:with-param name="style" select="'solid'"/>
											<xsl:with-param name="ruleweight"
												select="ancestor::table/@rule-weights"/>
										</xsl:call-template>
									</xsl:otherwise>
								</xsl:choose>
							</xsl:if>
							<xsl:if
								test="ancestor::tgroup/colspec[@colname=$currColname]/@rowsep='0'">
								<xsl:call-template name="RowSep">
									<!--<xsl:with-param name="color" select="'#C0C0C0'"/>-->
									<xsl:with-param name="color" select="'#FFFFFF'"/>
									<xsl:with-param name="style" select="'solid'"/>
									<xsl:with-param name="ruleweight" select="'0.0.0.0.0.0'"/>
								</xsl:call-template>
							</xsl:if>
							<xsl:if
								test="not(ancestor::tgroup/colspec[@colname=$currColname]/@rowsep)">
								<xsl:call-template name="RowSep">
									<!--<xsl:with-param name="color" select="'#C0C0C0'"/>-->
									<xsl:with-param name="color" select="'#FFFFFF'"/>
									<xsl:with-param name="style" select="'solid'"/>
									<xsl:with-param name="ruleweight" select="'0.0.0.0.0.0'"/>
								</xsl:call-template>
							</xsl:if>
						</xsl:if>
					</xsl:if>
				</xsl:if>
			</xsl:attribute>
			<span>
				<xsl:attribute name="class">
					<xsl:text>td</xsl:text>
				</xsl:attribute>
				<xsl:attribute name="style">
					<xsl:if test="ancestor::tgroup/@bearoff">
						<xsl:text>padding-left: </xsl:text>
						<xsl:value-of select="number(ancestor::tgroup/@bearoff) + 5"/>
						<xsl:text>px; </xsl:text>
						<xsl:text>padding-right: </xsl:text>
						<xsl:text>1px; </xsl:text>
					</xsl:if>
					<xsl:if test="not(ancestor::tgroup/@bearoff)">
						<xsl:text>padding-left:5px;padding-right:1px;</xsl:text>
					</xsl:if>
				</xsl:attribute>
				<!-- indent: &#160 -->
				<xsl:if test="@entry-modify">
					<xsl:call-template name="Indent">
						<xsl:with-param name="num"
							select="number(substring(@entry-modify, string-length(@entry-modify),1) -1)*2"
						/>
					</xsl:call-template>
				</xsl:if>
				<xsl:if test="@stub-hierarchy">
					<xsl:call-template name="Indent">
						<xsl:with-param name="num" select="(number(@stub-hierarchy)-1)*2"/>
					</xsl:call-template>
				</xsl:if>
				<!--xsl:if test="count(preceding-sibling::entry) =0">
					<xsl:if test="count(../preceding-sibling::row) =0"-->
				<!-- TB May 2009 fixing put quotes only for the first non empty column -->
				<xsl:variable name="isDutyTable">
					<xsl:choose>
						<xsl:when test="contains(ancestor::table/@table-template-name, 'Duty')">
							<xsl:text>yes</xsl:text>
						</xsl:when>
						<xsl:when test="contains(ancestor::table/@table-template-name, 'duty')">
							<xsl:text>yes</xsl:text>
						</xsl:when>
						<xsl:otherwise>no</xsl:otherwise>
					</xsl:choose>
				</xsl:variable>
				<xsl:choose>
					<xsl:when test="ancestor::quoted-block  and $isDutyTable='yes' and not(ancestor::table/@table-type='9-Duty-Suspension')">
						<xsl:if test="count(preceding-sibling::entry) =0">
							<xsl:if test="count(../preceding-sibling::row) =0">
								<xsl:if
									test="string-length(ancestor::table/ttitle) = 0 and string-length(ancestor::table/tdesc) =0 and string-length(ancestor::table/tgroup/thead) =0 ">
									<xsl:text disable-output-escaping="yes">“</xsl:text>
								</xsl:if>
							</xsl:if>
						</xsl:if>						
					</xsl:when>
					<xsl:when test="ancestor::quoted-block  and $isDutyTable='yes' and ancestor::table/@table-type='9-Duty-Suspension'">
						<xsl:if test="count(preceding-sibling::entry) =1">
							<xsl:if test="count(../preceding-sibling::row) =0">
								<xsl:if
									test="string-length(ancestor::table/ttitle) = 0 and string-length(ancestor::table/tdesc) =0 and string-length(ancestor::table/tgroup/thead) =0 ">
									<xsl:text disable-output-escaping="yes">“</xsl:text>
								</xsl:if>
							</xsl:if>
						</xsl:if>						
					</xsl:when>
					<xsl:when test="ancestor::quoted-block and $isFirstNonEmptyEntry='yes'">
						<xsl:if
							test="string-length(ancestor::table/ttitle) = 0 and string-length(ancestor::table/tdesc) =0 and string-length(ancestor::table/tgroup/thead) =0 ">
							<xsl:text disable-output-escaping="yes">“</xsl:text>
						</xsl:if>
					</xsl:when>
				</xsl:choose>				
				<xsl:apply-templates/>			
				<!-- closing quote -->
				<xsl:if test="ancestor::quoted-block and ancestor::quoted-block/after-quoted-block">
					<xsl:variable name="ParentQBNd">
						<xsl:value-of select="name(ancestor::quoted-block/child::*[1])"/>
					</xsl:variable>
					<xsl:variable name="ParentNd">
						<xsl:value-of select="name(ancestor::table/parent::*[1])"/>
					</xsl:variable>
					<xsl:variable name="LvlDiff">
						<xsl:call-template name="Getleveldiff">
							<xsl:with-param name="pnd1" select="$ParentQBNd"/>
							<xsl:with-param name="pnd2" select="$ParentNd"/>
						</xsl:call-template>
					</xsl:variable>
					<xsl:variable name="afterQBFlag">
						<xsl:choose>
							<xsl:when test="$LvlDiff='0'">
								<xsl:value-of select="2"/>
							</xsl:when>
							<xsl:when test="$LvlDiff='1'">
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) &gt; 0">
									<xsl:value-of select="1"/>
								</xsl:if>
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) = 0">
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
										<xsl:if
											test="name(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block'">
											<xsl:value-of select="2"/>
										</xsl:if>
										<xsl:if
											test="not(name(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block')">
											<xsl:value-of select="1"/>
										</xsl:if>
									</xsl:if>
								</xsl:if>
							</xsl:when>
							<xsl:when test="$LvlDiff=2">
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) &gt; 0">
									<xsl:value-of select="1"/>
								</xsl:if>
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) = 0">
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
										<xsl:value-of select="1"/>
									</xsl:if>
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
											<xsl:if
												test="name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block'">
												<xsl:value-of select="2"/>
											</xsl:if>
											<xsl:if
												test="not(name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block')">
												<xsl:value-of select="1"/>
											</xsl:if>
										</xsl:if>
									</xsl:if>
								</xsl:if>
							</xsl:when>
							<xsl:when test="$LvlDiff=3">
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) &gt; 0">
									<xsl:value-of select="1"/>
								</xsl:if>
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) = 0">
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
										<xsl:value-of select="1"/>
									</xsl:if>
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
											<xsl:value-of select="1"/>
										</xsl:if>
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
											<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:if
												test="name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block'">
												<xsl:value-of select="2"/>
												</xsl:if>
												<xsl:if
												test="not(name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block')">
												<xsl:value-of select="1"/>
												</xsl:if>
											</xsl:if>
										</xsl:if>
									</xsl:if>
								</xsl:if>
							</xsl:when>
							<xsl:when test="$LvlDiff=4">
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) &gt; 0">
									<xsl:value-of select="1"/>
								</xsl:if>
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) = 0">
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
										<xsl:value-of select="1"/>
									</xsl:if>
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
											<xsl:value-of select="1"/>
										</xsl:if>
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
											<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:value-of select="1"/>
											</xsl:if>

											<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:if
												test="name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block'">
												<xsl:value-of select="2"/>
												</xsl:if>
												<xsl:if
												test="not(name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block')">
												<xsl:value-of select="1"/>
												</xsl:if>
												</xsl:if>
											</xsl:if>
										</xsl:if>
									</xsl:if>
								</xsl:if>
							</xsl:when>
							<xsl:when test="$LvlDiff=5">
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) &gt; 0">
									<xsl:value-of select="1"/>
								</xsl:if>
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) = 0">
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
										<xsl:value-of select="1"/>
									</xsl:if>
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
											<xsl:value-of select="1"/>
										</xsl:if>
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
											<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:value-of select="1"/>
											</xsl:if>
											<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:value-of select="1"/>
												</xsl:if>
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:if
												test="name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block'">
												<xsl:value-of select="2"/>
												</xsl:if>
												<xsl:if
												test="not(name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block')">
												<xsl:value-of select="1"/>
												</xsl:if>
												</xsl:if>
												</xsl:if>
											</xsl:if>
										</xsl:if>
									</xsl:if>
								</xsl:if>
							</xsl:when>
							<xsl:when test="$LvlDiff=6">
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) &gt; 0">
									<xsl:value-of select="1"/>
								</xsl:if>
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) = 0">
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
										<xsl:value-of select="1"/>
									</xsl:if>
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
											<xsl:value-of select="1"/>
										</xsl:if>
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
											<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:value-of select="1"/>
											</xsl:if>
											<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:value-of select="1"/>
												</xsl:if>
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:value-of select="1"/>
												</xsl:if>
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:if
												test="name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block'">
												<xsl:value-of select="2"/>
												</xsl:if>
												<xsl:if
												test="not(name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block')">
												<xsl:value-of select="1"/>
												</xsl:if>
												</xsl:if>
												</xsl:if>
												</xsl:if>
											</xsl:if>
										</xsl:if>
									</xsl:if>
								</xsl:if>
							</xsl:when>
							<xsl:when test="$LvlDiff=7">
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) &gt; 0">
									<xsl:value-of select="1"/>
								</xsl:if>
								<xsl:if
									test="count(ancestor::table/parent::*[1]/following-sibling::*) = 0">
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
										<xsl:value-of select="1"/>
									</xsl:if>
									<xsl:if
										test="count(ancestor::table/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
											<xsl:value-of select="1"/>
										</xsl:if>
										<xsl:if
											test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
											<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:value-of select="1"/>
											</xsl:if>
											<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:value-of select="1"/>
												</xsl:if>
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:value-of select="1"/>
												</xsl:if>
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:value-of select="1"/>
												</xsl:if>
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) = 0">
												<xsl:if
												test="count(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*) &gt; 0">
												<xsl:if
												test="name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block'">
												<xsl:value-of select="2"/>
												</xsl:if>
												<xsl:if
												test="not(name(ancestor::table/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/parent::*[1]/following-sibling::*[1]) ='after-quoted-block')">
												<xsl:value-of select="1"/>
												</xsl:if>
												</xsl:if>
												</xsl:if>
												</xsl:if>
												</xsl:if>
											</xsl:if>
										</xsl:if>
									</xsl:if>
								</xsl:if>
							</xsl:when>
							<xsl:otherwise>
								<xsl:value-of select="1"/>
							</xsl:otherwise>
						</xsl:choose>
					</xsl:variable>
					<!--<xsl:if test="ancestor::table/following-sibling::after-quoted-block"> -->
					<!--<xsl:if test="ancestor::quoted-block and ancestor::quoted-block/after-quoted-block">-->
					<xsl:variable name="singleq">
						<xsl:if test="$afterQBFlag='2'">
							<xsl:text>”</xsl:text>
						</xsl:if>
					</xsl:variable>
					<xsl:variable name="qbdata">
						<!--<xsl:value-of select="concat($singleq, ancestor::table/following-sibling::after-quoted-block)"/> -->
						<xsl:if test="$afterQBFlag='2'">
							<xsl:value-of
								select="concat($singleq, ancestor::quoted-block/after-quoted-block)"
							/>
						</xsl:if>
						<!--<xsl:if test="not(name(ancestor::table/following-sibling::*[1])='after-quoted-block' or name(ancestor::subclause/following-sibling::*[1])='after-quoted-block' or name(ancestor::clause/following-sibling::*[1])='after-quoted-block' or name(ancestor::subparagraph/following-sibling::*[1])='after-quoted-block' or name(ancestor::paragraph/following-sibling::*[1])='after-quoted-block' or name(ancestor::subsection/following-sibling::*[1])='after-quoted-block' or name(ancestor::section/following-sibling::*[1])='after-quoted-block')">
							<xsl:text></xsl:text> 
						</xsl:if>-->
					</xsl:variable>
					<xsl:variable name="lastcell">
						<xsl:for-each select="ancestor::tbody//entry">
							<!-- TB change 11May2009  change in logic of last sell-->
							<xsl:variable name="isLastNonEmptyCell">
								<xsl:call-template name="isLasttNonemptyColumn"/>
							</xsl:variable>
							<xsl:if test="$isLastNonEmptyCell='yes'">
								<xsl:value-of select="substring(.,string-length(.),1)"/>
								</xsl:if>
							<!--xsl:if test="position()=last()">
								<xsl:value-of select="substring(.,string-length(.),1)"/>
							</xsl:if-->
						</xsl:for-each>
					</xsl:variable>
					<xsl:variable name="trailSpc">
						<xsl:if test="$lastcell= '.' or $lastcell=';'">
							<xsl:value-of select="concat($lastcell, $qbdata)"/>
						</xsl:if>
						<xsl:if test="not($lastcell= '.' or $lastcell=';')">
							<xsl:value-of select="$qbdata"/>
						</xsl:if>
					</xsl:variable>

					
					<!-- TB 11May2009 commented logic about last cell - to put wuotes at last NON EMPTY cell -->
					<xsl:variable name="isFormulaTable">
						<xsl:choose>
							<xsl:when test="contains(ancestor::table/@table-template-name, 'formula') or contains(ancestor::table/@table-template-name, 'Formula')">
								<xsl:text>true</xsl:text>
							</xsl:when>
							<xsl:otherwise>false</xsl:otherwise>
						</xsl:choose>
					</xsl:variable>
					<xsl:choose>
						<xsl:when test="$isFormulaTable='true'">
							<xsl:variable name="isLastNonEmptyCell_1">
								<xsl:call-template name="isLasttNonemptyColumn"/>
							</xsl:variable>
							<xsl:if test="$isLastNonEmptyCell_1 = 'yes' ">
								<xsl:value-of select="$qbdata"/>
							</xsl:if>
						</xsl:when>
						<xsl:otherwise>
							<xsl:if test="count(following-sibling::entry) = 0 ">
								<xsl:if test="count(../following-sibling::row) = 0">
									<xsl:value-of select="$qbdata"/>
								</xsl:if>								
							</xsl:if>
						</xsl:otherwise>
					</xsl:choose>
					
					
						
					<!--xsl:if test="count(following-sibling::entry) = 0 "-->
						<!-- TB 29Dec2008 Bug# 884 changed codition -->
						<!--xsl:if test="count(../following-sibling::row) &gt; 0"-->
						<!-- white out trailing space -->
						<!--xsl:if test="count(../following-sibling::row) =  0">								
							<span style="color:#FFFFFF">
								<xsl:value-of select="normalize-space($trailSpc)"/>
							</span>
						</xsl:if-->
						<!-- last row -->
						<!-- what testing environment displays is different from browser. maybe count(preceding-sibling) cause the different-->
						<!--<xsl:if test="count(../preceding-sibling::row) = 0 and count(../following-sibling::row) = 0">-->
						<!-- commented by TB 29Dec2008 Bug # 884 -->
						<!--xsl:if test="count(../following-sibling::row) = 0">
							<xsl:value-of select="$qbdata"/>
						</xsl:if>

					</xsl:if-->
				</xsl:if>

				<!--<xsl:if test="not(ancestor::table/following-sibling::after-quoted-block)"> -->
				<xsl:if
					test="not(ancestor::quoted-block  and ancestor::quoted-block/after-quoted-block)">
					<xsl:if test="count(following-sibling::entry) = 0 ">
						<xsl:variable name="lastcell">
							<xsl:for-each select="ancestor::tbody//entry">
								<xsl:if test="position()=last()">
									<xsl:value-of select="substring(.,string-length(.),1)"/>
								</xsl:if>
							</xsl:for-each>
						</xsl:variable>
						<xsl:if test="$lastcell = '.'  or $lastcell=';' or $lastcell='”'">
							<xsl:variable name="trailSpc">
								<xsl:value-of select="$lastcell"/>
							</xsl:variable>
							<xsl:if test="count(../following-sibling::row) &gt; 0">
								<xsl:choose>
									<xsl:when test="string-length($trailSpc)=1">
										<xsl:text>&#160;</xsl:text>
									</xsl:when>
									<xsl:otherwise>
										<xsl:text/>
									</xsl:otherwise>
								</xsl:choose>
							</xsl:if>
						</xsl:if>
					</xsl:if>
				</xsl:if>
			</span>
		</td>
	</xsl:template>

	<xsl:template match="linebreak">
		<br/>
	</xsl:template>

	<xsl:template
		match="//ttitle//processing-instruction()|//tdesc//processing-instruction()|//thead//processing-instruction()">
		<xsl:text disable-output-escaping="yes">&#160;</xsl:text>
	</xsl:template>
	<!-- end of table -->
	
	<!-- this template will be use for formula tables -->
	<!-- the quotes must be opened on the first column on the first non empty row -->
	<!--the suggestion that I am currently in the entry-->
	<xsl:template name="isFirstNonemptyColumn">
		<xsl:variable name="isFormulaTable">
			<xsl:choose>
				<xsl:when test="contains(ancestor::table/@table-template-name, 'formula') or contains(ancestor::table/@table-template-name, 'Formula')">
					<xsl:text>true</xsl:text>
				</xsl:when>
				<xsl:otherwise>false</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:choose>
			<!-- check for the Formula tables first - must be FIRST row -->			
			<xsl:when test="$isFormulaTable = 'true' and normalize-space(.) =''">
				<!-- empty column -->
				<xsl:text>no</xsl:text>
			</xsl:when>
			<xsl:when test="$isFormulaTable = 'true'  and count(preceding-sibling::entry) > 0 ">
				<!-- not the first column -->
				<xsl:text>no</xsl:text>
			</xsl:when>
			<xsl:when test="$isFormulaTable = 'true'  and  (parent::row/preceding-sibling::*[1]/child::*[1]/text() != '' or parent::row/preceding-sibling::*[1]/child::*[1]/child::*[1]/text() != '' )">
				<!-- not the first column -->
				<xsl:text>no</xsl:text>
			</xsl:when>
			<xsl:when test="$isFormulaTable = 'true' ">
				<!-- Otherwise for formula tables -->
				<xsl:text>yes</xsl:text>
			</xsl:when>
			<!-- not formula tables -->
			<xsl:when test="normalize-space(.) ='' and normalize-space(parent::row/preceding-sibling::row/entry) != ''">
				<xsl:text>no</xsl:text>
			</xsl:when>
			<!--xsl:when test="normalize-space(./preceding-sibling::row/entry) != ''"-->
			<xsl:when test="normalize-space(parent::row/preceding-sibling::row/entry) != ''">
				<xsl:text>no</xsl:text>
			</xsl:when>
			<xsl:when test="normalize-space(preceding-sibling::entry) != ''">
				<xsl:text>no</xsl:text>
			</xsl:when>
			<xsl:otherwise>
				<xsl:text>yes</xsl:text>
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	
	<xsl:template name="isLasttNonemptyColumn">
		<xsl:variable name="isFormulaTable">
			<xsl:choose>
				<xsl:when test="contains(ancestor::table/@table-template-name, 'formula') or contains(ancestor::table/@table-template-name, 'Formula')">
					<xsl:text>true</xsl:text>
				</xsl:when>
				<xsl:otherwise>false</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:choose>
			<!-- check for the Formula tables first - must be FIRST row -->			
			<xsl:when test="$isFormulaTable = 'true' and normalize-space(.) =''">
				<!-- empty column -->
				<xsl:text>no</xsl:text>
			</xsl:when>
			<xsl:when test="$isFormulaTable = 'true'  and count(following-sibling::entry) > 0 ">
				<!-- not the first column -->
				<xsl:text>no</xsl:text>
			</xsl:when>
			<xsl:when test="$isFormulaTable = 'true'  and  (parent::row/following-sibling::*[position()=last()]/child::*[position()=last()]/text() != '' or parent::row/following-sibling::*[position()=last()]/child::*[position()=last()]/child::*[position()=last()]/text() != '' )">
				<!-- not the first column -->
				<xsl:text>no</xsl:text>
			</xsl:when>
			<xsl:when test="$isFormulaTable = 'true' ">
				<!-- Otherwise for formula tables -->
				<xsl:text>yes</xsl:text>
			</xsl:when>
			<!-- not formula tables -->
			<xsl:when test="normalize-space(.) ='' and normalize-space(./following-sibling::row/entry) != ''">
				<xsl:text>no</xsl:text>
			</xsl:when>
			<xsl:otherwise>
				<xsl:text>yes</xsl:text>
			</xsl:otherwise>
		</xsl:choose>	
	</xsl:template>
	
	<!-- this template will calculate the max row lenght - will be used for determination of  formulas width-->
	<!-- Evaluation for forst  -->
	<xsl:template name="calcFormulaTableWidth">		
		<xsl:variable name="firstRowLength">
			<xsl:choose>
				<xsl:when test="tgroup/tbody/row[1]">
					<xsl:call-template name="theRowLength">	
						<xsl:with-param name="aRowNumber">
							<xsl:text>1</xsl:text>
						</xsl:with-param>
					</xsl:call-template>
				</xsl:when>
				<xsl:otherwise>
					<xsl:text>0</xsl:text>
				</xsl:otherwise>
			</xsl:choose>	
		</xsl:variable>
		<xsl:variable name="secondRowLength">
			<xsl:choose>
				<xsl:when test="tgroup/tbody/row[2]">
					<xsl:call-template name="theRowLength">	
						<xsl:with-param name="aRowNumber">
							<xsl:text>2</xsl:text>
						</xsl:with-param>
					</xsl:call-template>
				</xsl:when>
				<xsl:otherwise>
					<xsl:text>0</xsl:text>
				</xsl:otherwise>
			</xsl:choose>	
		</xsl:variable>
		<xsl:variable name="thirdRowLength">
			<xsl:choose>
				<xsl:when test="tgroup/tbody/row[3]">
					<xsl:call-template name="theRowLength">	
						<xsl:with-param name="aRowNumber">
							<xsl:text>3</xsl:text>
						</xsl:with-param>
					</xsl:call-template>
				</xsl:when>
				<xsl:otherwise>
					<xsl:text>0</xsl:text>
				</xsl:otherwise>
			</xsl:choose>	
		</xsl:variable>
		<xsl:choose>
			<!-- 1st >= 2nd and 1st >= 3rd -->
			<xsl:when test="number($firstRowLength) >= number($secondRowLength) and number($firstRowLength) >= number($thirdRowLength) ">
				<xsl:value-of select="$firstRowLength"/>
			</xsl:when>			
			<!--2nd >= 1st and 2nd >= 3rd -->
			<xsl:when test="number($secondRowLength) >= number($firstRowLength) and number($secondRowLength) >= number($thirdRowLength)">
				<xsl:value-of select="$secondRowLength"/>
			</xsl:when>			
			<!--3rd >= 1st and3rd >= 2nd -->
			<xsl:when test="number($thirdRowLength) >= number($firstRowLength) and number($thirdRowLength) >= number($secondRowLength) ">
				<xsl:value-of select="$thirdRowLength"/>
			</xsl:when>
		</xsl:choose>		
	</xsl:template>
	
	<!-- Evaluation of 3 first columns - for formulas only - suggesion - the only three columns for the formula -->
	<xsl:template name="theRowLength">
		<xsl:param name="aRowNumber"/>			
			<xsl:variable name="firstCellLength">
				<xsl:choose>
					<xsl:when test="tgroup/tbody/row[number($aRowNumber)]/entry[1]">
						<xsl:call-template name="singleCellLenght">
							<xsl:with-param name="aRowNumber" select="$aRowNumber"/>
							<xsl:with-param name="aCellNumber">
								<xsl:text>1</xsl:text>
							</xsl:with-param>
						</xsl:call-template>
					</xsl:when>
					<xsl:otherwise>
						<xsl:text>0</xsl:text>
					</xsl:otherwise>
				</xsl:choose>
			</xsl:variable>
		<xsl:variable name="secondCellLength">
			<xsl:choose>
				<xsl:when test="tgroup/tbody/row[number($aRowNumber)]/entry[2]">
					<xsl:call-template name="singleCellLenght">
						<xsl:with-param name="aRowNumber" select="$aRowNumber"/>
						<xsl:with-param name="aCellNumber">
							<xsl:text>2</xsl:text>
						</xsl:with-param>
					</xsl:call-template>
				</xsl:when>
				<xsl:otherwise>
					<xsl:text>0</xsl:text>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:variable name="thirdCellLength">
			<xsl:choose>
				<xsl:when test="tgroup/tbody/row[number($aRowNumber)]/entry[3]">
					<xsl:call-template name="singleCellLenght">
						<xsl:with-param name="aRowNumber" select="$aRowNumber"/>
						<xsl:with-param name="aCellNumber">
							<xsl:text>3</xsl:text>
						</xsl:with-param>
					</xsl:call-template>
				</xsl:when>
				<xsl:otherwise>
					<xsl:text>0</xsl:text>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		
		<xsl:value-of select="number($firstCellLength) + number($secondCellLength) + number($thirdCellLength)"/>
		
	</xsl:template>
	
	<xsl:template name="singleCellLenght">
		<xsl:param name="aRowNumber"/>
		<xsl:param name="aCellNumber"/>		
			<xsl:choose>
				<xsl:when test="tgroup/tbody/row[number[$aRowNumber]]/entry[number($aCellNumber)]/child::*">
					<xsl:value-of select="string-length(tgroup/tbody/row[$aRowNumber]/entry[$aCellNumber]/child::*[1]/text())"/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of select="string-length(tgroup/tbody/row[$aRowNumber]/entry[$aCellNumber]/text())"/>
				</xsl:otherwise>
			</xsl:choose>
	</xsl:template>

</xsl:stylesheet>
<!-- Stylus Studio meta-information - (c)1998-2003 Copyright Sonic Software Corporation. All rights reserved.
<metaInformation>
<scenarios/><MapperInfo srcSchemaPath="" srcSchemaRoot="" srcSchemaPathIsRelative="yes" srcSchemaInterpretAsXML="no" destSchemaPath="" destSchemaRoot="" destSchemaPathIsRelative="yes" destSchemaInterpretAsXML="no"/>
</metaInformation>
-->
